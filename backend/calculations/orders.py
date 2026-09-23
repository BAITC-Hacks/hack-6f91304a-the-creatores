"""Order arithmetic and auditable, deterministic replenishment recommendations."""

from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal
from math import isfinite

from backend.calculations.demand import forecast_demand
from backend.models import CalculationParameters


def _number(value, field, *, positive=False):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field}: ожидается число")
    number = float(value)
    if not isfinite(number) or number < 0 or (positive and number == 0):
        raise ValueError(f"{field}: некорректное количество")
    return number


def round_order_qty(need, moq=None, order_multiple=None):
    """Apply minimum order then package multiple, without inventing either constraint."""
    if isinstance(need, bool) or not isfinite(float(need)):
        raise ValueError("need: ожидается конечное число")
    minimum = _number(moq, "moq")
    multiple = _number(order_multiple, "order_multiple", positive=True)
    if need <= 0:
        return 0.0
    quantity = max(Decimal(str(need)), Decimal(str(minimum or 0)))
    if multiple is not None:
        step = Decimal(str(multiple))
        steps = quantity / step
        nearest = steps.to_integral_value(rounding=ROUND_HALF_EVEN)
        # Upstream weighted means use floats. A few ulps above a package boundary
        # must not add a whole package. Never erase a positive order or violate MOQ.
        if (
            nearest > 0
            and abs(steps - nearest) <= Decimal("1e-12")
            and nearest * step >= Decimal(str(minimum or 0))
        ):
            steps = nearest
        quantity = steps.to_integral_value(rounding=ROUND_CEILING) * step
    result = float(quantity)
    if not isfinite(result):
        raise ValueError("Количество заказа превышает числовой диапазон")
    return result


def incoming_in_period(product, start, end):
    """Return quantity or unknown, counted dated shipments, and warnings.

    The interval is [start, end). An explicit zero needs no ETA. Undated positive
    quantities invalidate the aggregate; overdue quantities are excluded with a warning.
    """
    warnings = []
    counted = []
    unknown = not product.get("incoming_known", False)
    if unknown:
        warnings.append("Нет полных данных о товарах в пути; поступления неизвестны.")
    total = Decimal(0)
    for shipment in product.get("incoming", []):
        quantity = _number(shipment.get("quantity"), "incoming.quantity")
        if quantity is None:
            unknown = True
            warnings.append("У поставки отсутствует количество; поступления неизвестны.")
            continue
        if quantity == 0:
            continue
        eta = shipment.get("date")
        if not eta:
            unknown = True
            warnings.append("У товара в пути нет даты прибытия; включение в период неизвестно.")
            continue
        eta = date.fromisoformat(eta) if isinstance(eta, str) else eta
        if eta < start:
            warnings.append(
                f"Поставка от {eta.isoformat()} просрочена и исключена; уточните её статус."
            )
        elif eta < end:
            total += Decimal(str(quantity))
            counted.append({"date": eta.isoformat(), "quantity": quantity})
    quantity = float(total)
    if not isfinite(quantity):
        unknown = True
        warnings.append("Сумма поступлений превышает числовой диапазон; количество неизвестно.")
    return (None if unknown else quantity), counted, list(dict.fromkeys(warnings))


def _projected_shortage(stock, daily, shipments, start, horizon_days):
    """Heuristic using horizon-average daily demand; receipts arrive at day's start."""
    balance = stock
    previous = start
    receipt = start + timedelta(days=horizon_days)
    for shipment in sorted(shipments, key=lambda item: item["date"]):
        arrival = date.fromisoformat(shipment["date"])
        if arrival >= receipt:
            break
        balance -= daily * (arrival - previous).days
        if balance < -1e-9:
            return True
        balance += shipment["quantity"]
        previous = arrival
    return balance - daily * (receipt - previous).days < -1e-9


def calculate_order(product, parameters, *, forecast_options=None):
    """Return a recommendation including ``explanation`` (for the detailed API).

    Parameters' lead time is an explicit scenario override, as required by the
    existing backend contract. The file lead time is retained and compared below.
    """
    params = CalculationParameters.model_validate(parameters)
    start = params.calculation_date
    end = start + timedelta(days=params.lead_time_days + params.review_period_days)
    forecast = forecast_demand(
        product.get("sales", []),
        start,
        end,
        seasonality=product.get("seasonality") or None,
        growth_adjustment=params.demand_growth_adjustment,
        **(forecast_options or {}),
    )
    stock = _number(product.get("stock"), "stock")
    moq = _number(product.get("moq"), "moq")
    multiple = _number(product.get("order_multiple"), "order_multiple", positive=True)
    incoming, shipments, incoming_warnings = incoming_in_period(product, start, end)
    demand = _number(forecast["forecast_demand"], "forecast_demand")
    daily = _number(forecast["daily_demand"], "daily_demand")
    safety = None if daily is None else float(Decimal(str(daily)) * params.safety_stock_days)
    warnings = list(product.get("warnings", [])) + forecast["warnings"] + incoming_warnings
    if safety is not None and not isfinite(safety):
        safety = None
        warnings.append("Страховой запас превышает числовой диапазон; количество неизвестно.")
    for value, message in (
        (stock, "Нет текущего остатка; количество заказа неизвестно."),
        (moq, "MOQ не указан; ограничение минимальной партии не применялось."),
        (multiple, "Кратность упаковки не указана; округление по упаковке не применялось."),
        (product.get("unit"), "Единица измерения не указана; проверьте единицы исходных данных."),
    ):
        if value is None:
            warnings.append(message)
    file_lead = product.get("lead_time_days")
    if file_lead is None:
        warnings.append(
            "В Excel нет срока поставки; использован явно заданный срок "
            f"{params.lead_time_days} дн. из параметров расчёта."
        )
    elif file_lead != params.lead_time_days:
        warnings.append(
            f"Срок поставки из Excel ({file_lead:g} дн.) переопределён "
            f"параметром расчёта ({params.lead_time_days} дн.)."
        )
    raw_need = None
    recommended = None
    urgency = "unknown"
    if all(value is not None for value in (demand, safety, stock, incoming)):
        raw_need = float(
            Decimal(str(demand))
            + Decimal(str(safety))
            - Decimal(str(stock))
            - Decimal(str(incoming))
        )
        if not isfinite(raw_need):
            raw_need = None
            warnings.append("Потребность превышает числовой диапазон; заказ неизвестен.")
        else:
            try:
                recommended = round_order_qty(raw_need, moq, multiple)
            except ValueError:
                warnings.append("Заказ после округления превышает числовой диапазон.")
    if recommended is not None:
        projected_receipts = list(shipments)
        if recommended > 0:
            projected_receipts.append(
                {
                    "date": (start + timedelta(days=params.lead_time_days)).isoformat(),
                    "quantity": recommended,
                }
            )
        timing_shortage = _projected_shortage(
            stock, daily, projected_receipts, start, (end - start).days
        )
        urgency = "high" if timing_shortage else ("medium" if recommended > 0 else "none")
        reason = (
            f"За период [{start.isoformat()}, {end.isoformat()}): спрос {demand:g} "
            f"+ страховой запас {safety:g} − остаток {stock:g} "
            f"− поставки в периоде {incoming:g} = потребность {raw_need:g}. "
        )
        if recommended > 0:
            reason += f"Запаса недостаточно; заказ с учётом ограничений: {recommended:g}."
        else:
            reason += "Суммарной доступности достаточно; заказ равен 0."
        if timing_shortage:
            warnings.append(
                "Возможен временный дефицит в периоде с учётом дат поступлений "
                "и предполагаемого прибытия рекомендованного заказа; "
                "срочность оценена по среднесуточному прогнозу."
            )
    else:
        missing = [
            name
            for name, value in (
                ("спрос", demand),
                ("страховой запас", safety),
                ("остаток", stock),
                ("поступления в периоде", incoming),
            )
            if value is None
        ]
        reason = (
            "Недостаточно данных для заказа: " + ", ".join(missing) + "."
            if missing
            else "Количество заказа выходит за поддерживаемый числовой диапазон."
        )
    if daily is not None:
        reason += (
            f" Базовый спрос {forecast['base_daily_demand']:g}/день; "
            f"коэффициент сезонности {forecast['seasonal_factor']:g}; "
            f"скорректировано аномалий: {len(forecast['anomalies'])}."
        )
    return {
        "sku": product["sku"],
        "name": product.get("name"),
        "supplier": product.get("supplier"),
        "unit": product.get("unit"),
        "stock": stock,
        "incoming_in_period": incoming,
        "forecast_demand": demand,
        "safety_stock": safety,
        "moq": moq,
        "order_multiple": multiple,
        "recommended_qty": recommended,
        "urgency": urgency,
        "reason": reason,
        "warnings": list(dict.fromkeys(warnings)),
        "explanation": {
            "algorithm": "weighted-daily-demand-v1",
            "period": {"start": start.isoformat(), "end_exclusive": end.isoformat()},
            "parameters": params.model_dump(mode="json"),
            "forecast": forecast,
            "stock": stock,
            "incoming": incoming,
            "counted_shipments": shipments,
            "safety_stock": safety,
            "source_lead_time_days": file_lead,
            "effective_lead_time_days": params.lead_time_days,
            "moq": moq,
            "order_multiple": multiple,
            "raw_need": raw_need,
            "nonnegative_need": None if raw_need is None else max(0.0, raw_need),
            "recommended_qty": recommended,
            "urgency_method": "average_daily_demand_with_proposed_receipt_over_horizon",
        },
    }
