"""Deterministic monthly-sales baseline with conservative, inspectable adjustments.

Only complete calendar months before ``start_date`` participate. A missing month
is unknown, never zero. Monthly sales are divided by observed in-stock days when
those days are known; this estimates a rate and does not assert a lost-sales total.
The forecast period is half-open: [start_date, end_date).
"""

from __future__ import annotations

import calendar
import math
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

DEFAULT_LOOKBACK_MONTHS = 6
DEFAULT_SPIKE_MULTIPLIER = 3.0
DEFAULT_TREND_MIN_MONTHS = 4
DEFAULT_TREND_THRESHOLD = 0.03
DEFAULT_MAX_TREND_ADJUSTMENT = 0.25
MIN_SEASONALITY_MONTHS = 24


def _median(values: Iterable[float]) -> float:
    """Median without overflowing the sum of the two middle finite values."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else ordered[middle - 1] / 2 + ordered[middle] / 2


def _date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("Ожидалась дата ISO YYYY-MM-DD или datetime.date")


def _month_shift(value: date, amount: int) -> date:
    index = value.year * 12 + value.month - 1 + amount
    return date(index // 12, index % 12 + 1, 1)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, (bool, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _slope(points: list[tuple[int, float]]) -> float:
    """Theil–Sen slope: a single endpoint cannot determine the fitted slope."""
    slopes = [
        (right_y - left_y) / (right_x - left_x)
        for index, (left_x, left_y) in enumerate(points)
        for right_x, right_y in points[index + 1 :]
        if right_x != left_x
    ]
    return _median(slopes) if slopes else 0.0


def _seasonality(
    supplied: Mapping[int | str, float | None] | None,
    rows: list[dict[str, Any]],
    cutoff: date,
    spike_multiplier: float,
    warnings: list[str],
) -> tuple[dict[int, float], str]:
    neutral = dict.fromkeys(range(1, 13), 1.0)
    if supplied:
        factors = neutral.copy()
        supplied_months = set()
        for key, raw in supplied.items():
            try:
                month = int(key)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Месяц сезонности должен быть целым от 1 до 12") from exc
            if (
                isinstance(key, bool)
                or str(key) not in {str(month), f"{month:02d}"}
                or month not in neutral
            ):
                raise ValueError("Сезонность: месяц 1–12, коэффициент — конечное число > 0")
            if month in supplied_months:
                raise ValueError("Дублирующийся месяц сезонности")
            if raw is None:
                warnings.append(
                    f"Не задан коэффициент сезонности для месяца {month}; "
                    "использован коэффициент 1."
                )
                continue
            factor = _number(raw)
            if factor is None or factor <= 0:
                raise ValueError("Сезонность: коэффициент должен быть конечным числом > 0")
            factors[month] = factor
            supplied_months.add(month)
        if len(supplied_months) < 12:
            warnings.append("Для месяцев без заданной сезонности принят нейтральный коэффициент 1.")
        return factors, "explicit" if supplied_months else "neutral"

    first = _month_shift(cutoff, -MIN_SEASONALITY_MONTHS)
    history = [row for row in rows if row["date"] >= first]
    expected = [_month_shift(first, offset) for offset in range(MIN_SEASONALITY_MONTHS)]
    if [row["date"] for row in history] != expected or any(
        row["rate"] <= 0 or row["exposure_days"] < 7 for row in history
    ):
        warnings.append(
            "Сезонность не определена: нужны 24 последовательных полных месяца "
            "с положительными продажами и достаточным числом дней в наличии; коэффициент 1."
        )
        return neutral, "neutral"

    # Remove a robust log-linear trend before comparing annual repetitions. The
    # fit uses the full, independent 24-month history, never the clipped baseline.
    logs = [math.log(row["rate"]) for row in history]
    log_slope = _slope(list(enumerate(logs)))
    centered = [value - log_slope * index for index, value in enumerate(logs)]
    annual_centers = [_median(centered[:12]), _median(centered[12:])]
    ratios = [
        centered[index] - annual_centers[index // 12] for index in range(MIN_SEASONALITY_MONTHS)
    ]
    # With only two annual observations, a discordant peak cannot reliably be
    # distinguished from a one-off deal. Decline inference for the whole pattern.
    if any(
        abs(ratios[index] - ratios[index + 12]) > math.log(spike_multiplier) for index in range(12)
    ):
        warnings.append(
            "Сезонность не определена: годовые повторения противоречивы или содержат "
            "аномальный всплеск; коэффициент 1."
        )
        return neutral, "neutral"
    monthly_logs = [(ratios[index] + ratios[index + 12]) / 2 for index in range(12)]
    # Log centering prevents overflow even for valid, very large input values.
    peak = max(monthly_logs)
    values = [math.exp(value - peak) for value in monthly_logs]
    average = sum(values) / 12
    factors = {history[index]["date"].month: value / average for index, value in enumerate(values)}
    if any(value <= 0 for value in factors.values()):
        warnings.append("Нестабильные сезонные коэффициенты; использован коэффициент 1.")
        return neutral, "neutral"
    warnings.append("Сезонность оценена по двум полным годам; это оценка, а не заданное условие.")
    return factors, "inferred"


def forecast_demand(
    sales: Iterable[Mapping[str, Any]],
    start_date: date | str,
    end_date: date | str,
    *,
    seasonality: Mapping[int | str, float | None] | None = None,
    growth_adjustment: float | None = None,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    spike_multiplier: float = DEFAULT_SPIKE_MULTIPLIER,
    trend_min_months: int = DEFAULT_TREND_MIN_MONTHS,
    trend_threshold: float = DEFAULT_TREND_THRESHOLD,
    max_trend_adjustment: float = DEFAULT_MAX_TREND_ADJUSTMENT,
    apply_trend: bool = True,
) -> dict[str, Any]:
    """Forecast demand and return JSON-serializable calculation evidence.

    ``sales`` has ``month`` (first of month), ``quantity`` and optional
    ``stockout_days``. Records must represent complete monthly totals.
    ``seasonality`` maps month numbers to strictly positive relative factors;
    history is deseasonalized before the target factors are applied. The baseline
    weights each month by its position in the calendar lookback window (1..N).

    High daily rates are winsorized at median + max(3*MAD, 2*median), with 2
    replaced by ``spike_multiplier - 1``. Two observations use the lower rate as
    the reference; one observation cannot support anomaly or trend detection.
    A trend needs >=4 consecutive unadjusted months and >=2/3 directional steps.
    Its bounded continuation is projected to the target-period midpoint from the
    weighted historical midpoint. An explicit ``growth_adjustment`` (e.g. .1)
    overrides the automatically applied trend with factor 1.1.
    """
    start, end = _date(start_date), _date(end_date)
    if end <= start:
        raise ValueError("Конец периода должен быть позже начала (правая граница исключена)")
    if (
        isinstance(lookback_months, bool)
        or not isinstance(lookback_months, int)
        or lookback_months < 1
    ):
        raise ValueError("lookback_months должен быть положительным целым числом")
    if (
        isinstance(trend_min_months, bool)
        or not isinstance(trend_min_months, int)
        or trend_min_months < 4
    ):
        raise ValueError("Для тренда нужны минимум 4 месяца")
    for name, value, lower, upper in (
        ("spike_multiplier", spike_multiplier, 1, math.inf),
        ("trend_threshold", trend_threshold, 0, 1),
        ("max_trend_adjustment", max_trend_adjustment, 0, 1),
    ):
        number = _number(value)
        if (
            number is None
            or number < lower
            or number > upper
            or (name == "spike_multiplier" and number == 1)
        ):
            raise ValueError(f"Некорректный параметр {name}")
    if growth_adjustment is not None:
        adjustment = _number(growth_adjustment)
        if adjustment is None or not -1 <= adjustment <= 5:
            raise ValueError("growth_adjustment должен быть от -1 до 5")
    else:
        adjustment = None

    warnings: list[str] = []
    cutoff = start.replace(day=1)
    first = _month_shift(cutoff, -lookback_months)
    candidates: dict[date, list[Mapping[str, Any]]] = {}
    ignored_future = 0
    for row in sales:
        if not isinstance(row, Mapping):
            warnings.append("Запись продаж неверного формата исключена.")
            continue
        try:
            month = _date(row.get("month"))
        except (TypeError, ValueError):
            warnings.append("Запись продаж с некорректной датой исключена.")
            continue
        if month.day != 1:
            warnings.append(
                f"Продажи {month.isoformat()}: дата не является началом месяца; исключены."
            )
            continue
        if month >= cutoff:
            ignored_future += 1
            continue
        candidates.setdefault(month, []).append(row)
    if ignored_future:
        warnings.append(
            f"Текущий незавершённый и будущие месяцы исключены из истории: {ignored_future}."
        )

    rows = []
    for month, same_month in sorted(candidates.items()):
        label = month.isoformat()
        if len(same_month) != 1:
            warnings.append(
                f"Дубли продаж за {label} исключены; автоматическое суммирование не выполнено."
            )
            continue
        row = same_month[0]
        quantity = _number(row.get("quantity"))
        if quantity is None or quantity < 0:
            warnings.append(f"Нет корректного количества продаж за {label}; месяц исключён.")
            continue
        days = calendar.monthrange(month.year, month.month)[1]
        raw_stockout = row.get("stockout_days")
        stockout = _number(raw_stockout)
        if raw_stockout is not None and (stockout is None or not 0 <= stockout <= days):
            warnings.append(f"Некорректные дни отсутствия товара за {label}; месяц исключён.")
            continue
        if stockout is None:
            warnings.append(
                "Нет полной истории наличия товара: lost sales достоверно определить нельзя; "
                "скрытый спрос не добавлялся."
            )
            if quantity == 0:
                warnings.append(
                    f"Нулевые продажи за {label}: неизвестно, отсутствовал ли товар; "
                    "ноль сохранён как наблюдение, возможна недооценка спроса."
                )
        exposure = days - (stockout or 0)
        if exposure == 0:
            warnings.append(f"Товар отсутствовал весь месяц {label}; месяц исключён из среднего.")
            continue
        if stockout and quantity == 0:
            # Some observed days remain, so zero is still real evidence, but is
            # explicitly uncertain. Fully unavailable months were removed above.
            warnings.append(
                f"Нулевые продажи за {label} при частичном отсутствии товара: "
                "спрос в отсутствующие дни неизвестен; lost sales не добавлялись."
            )
        elif stockout:
            warnings.append(
                f"Спрос за {label} оценён по {exposure:g} дням наличия; "
                "это допущение о темпе продаж, фактические lost sales неизвестны."
            )
        rate = quantity / exposure
        if not math.isfinite(rate):
            warnings.append(f"Спрос за {label} превышает числовой диапазон; месяц исключён.")
            continue
        rows.append(
            {
                "date": month,
                "quantity": quantity,
                "days": days,
                "stockout_days": stockout,
                "exposure_days": exposure,
                "rate": rate,
            }
        )

    factors, seasonal_source = _seasonality(seasonality, rows, cutoff, spike_multiplier, warnings)
    recent = [dict(row) for row in rows if row["date"] >= first]
    for row in recent:
        row["base_rate"] = row["rate"] / factors[row["date"].month]
    if any(not math.isfinite(row["base_rate"]) for row in recent):
        warnings.append(
            "Часть наблюдений исключена: слишком большой спрос после поправки сезонности."
        )
        recent = [row for row in recent if math.isfinite(row["base_rate"])]
    observed = {row["date"] for row in recent}
    missing = [
        _month_shift(first, offset).isoformat()
        for offset in range(lookback_months)
        if _month_shift(first, offset) not in observed
    ]
    if missing:
        warnings.append(
            "Нет пригодных наблюдений за месяцы: "
            + ", ".join(missing)
            + "; отсутствующие месяцы не заменялись нулём."
        )
    if len(recent) < trend_min_months:
        warnings.append(
            "Короткая история продаж: надёжность прогноза и поиска аномалий ограничена."
        )

    rates = [row["base_rate"] for row in recent]
    cap = None
    if len(rates) >= 2:
        center = min(rates) if len(rates) == 2 else _median(rates)
        mad = 0.0 if len(rates) == 2 else _median(abs(value - center) for value in rates)
        cap = min(max(rates), center + max(3 * mad, center * (spike_multiplier - 1)))
    anomalies = []
    total_weight = 0
    for row in recent:
        row["adjusted_rate"] = min(row["base_rate"], cap) if cap is not None else row["base_rate"]
        row["weight"] = (row["date"].year - first.year) * 12 + row["date"].month - first.month + 1
        total_weight += row["weight"]
        if row["adjusted_rate"] < row["base_rate"]:
            anomalies.append(
                {
                    "month": row["date"].isoformat(),
                    "original_quantity": row["quantity"],
                    "original_daily_demand": row["base_rate"],
                    "adjusted_daily_demand": row["adjusted_rate"],
                    "adjusted_quantity": (row["adjusted_rate"] / row["base_rate"])
                    * row["quantity"],
                    "method": "robust_upper_clip",
                }
            )
    if anomalies:
        warnings.append(
            f"Скорректированы аномальные всплески: {len(anomalies)}; "
            "разовые крупные продажи ограничены при расчёте среднего."
        )
    base = (
        sum(row["adjusted_rate"] * (row["weight"] / total_weight) for row in recent)
        if recent
        else None
    )
    if base is not None and not math.isfinite(base):
        base = None
        warnings.append("Базовый спрос превышает числовой диапазон; расчёт недоступен.")

    trend: dict[str, Any] = {
        "classification": "insufficient_data",
        "monthly_rate": None,
        "factor": 1.0,
        "source": "neutral",
        "supporting_steps": 0,
        "months": len(recent),
        "projection_months": None,
    }
    consecutive = all(
        _month_shift(left["date"], 1) == right["date"] for left, right in zip(recent, recent[1:])
    )
    if len(recent) >= trend_min_months and consecutive and not anomalies:
        fitted_slope = _slope(list(enumerate(rates)))
        center = _median(rates)
        monthly_rate = fitted_slope / center if center > 0 else 0.0
        sign = 1 if monthly_rate > 0 else -1
        supporting = sum(
            (right - left) * sign > center * 0.005 for left, right in zip(rates, rates[1:])
        )
        enough_support = supporting >= max(2, math.ceil((len(recent) - 1) * 2 / 3))
        classification = "stable"
        if abs(monthly_rate) >= trend_threshold and enough_support:
            classification = "growth" if monthly_rate > 0 else "decline"
        weighted_midpoint = sum(
            (row["date"].toordinal() + row["days"] / 2) * row["weight"] / total_weight
            for row in recent
        )
        target_midpoint = start.toordinal() + (end - start).days / 2
        projection = max(0, (target_midpoint - weighted_midpoint) / (365.25 / 12))
        change = max(-max_trend_adjustment, min(max_trend_adjustment, monthly_rate * projection))
        trend.update(
            {
                "classification": classification,
                "monthly_rate": monthly_rate,
                "supporting_steps": supporting,
                "projection_months": projection,
            }
        )
        if apply_trend and classification != "stable":
            trend.update(factor=1 + change, source="estimated")
    if trend["classification"] == "insufficient_data":
        warnings.append(
            "Устойчивый тренд не определён: мало последовательных месяцев без аномалий."
        )
    if adjustment is not None:
        trend.update(factor=1 + adjustment, source="explicit")

    days = (end - start).days
    weighted_seasonality = 0.0
    cursor = start
    while cursor < end:
        boundary = min(end, _month_shift(cursor.replace(day=1), 1))
        weighted_seasonality += factors[cursor.month] * ((boundary - cursor).days / days)
        cursor = boundary
    daily = base * trend["factor"] * weighted_seasonality if base is not None else None
    forecast = daily * days if daily is not None else None
    if forecast is not None and not math.isfinite(forecast):
        forecast = daily = None
        warnings.append("Прогноз превышает числовой диапазон; расчёт количества недоступен.")
    if base is None:
        warnings.append("Нет пригодной истории продаж; спрос не рассчитан и не заменён нулём.")

    return {
        "forecast_demand": forecast,
        "base_daily_demand": base,
        "daily_demand": daily,
        "seasonal_factor": weighted_seasonality,
        "seasonality_source": seasonal_source,
        "seasonality": {str(month): factor for month, factor in factors.items()},
        "trend": trend,
        "anomalies": anomalies,
        "used_period": {
            "start": recent[0]["date"].isoformat() if recent else None,
            "end": _month_shift(recent[-1]["date"], 1).isoformat() if recent else None,
            "months": [row["date"].isoformat() for row in recent],
            "requested_start": first.isoformat(),
            "requested_end": cutoff.isoformat(),
            "missing_months": missing,
        },
        "forecast_period": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "observations": [
            {
                "month": row["date"].isoformat(),
                "quantity": row["quantity"],
                "stockout_days": row["stockout_days"],
                "exposure_days": row["exposure_days"],
                "daily_demand": row["rate"],
                "adjusted_base_daily_demand": row["adjusted_rate"],
                "weight": row["weight"],
            }
            for row in recent
        ],
        "parameters": {
            "lookback_months": lookback_months,
            "spike_multiplier": spike_multiplier,
            "trend_min_months": trend_min_months,
            "trend_threshold": trend_threshold,
            "max_trend_adjustment": max_trend_adjustment,
            "apply_trend": apply_trend,
            "growth_adjustment": adjustment,
        },
        "warnings": list(dict.fromkeys(warnings)),
    }
