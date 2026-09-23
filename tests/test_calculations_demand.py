import calendar
import copy
import json
from datetime import date

import pytest

from backend.calculations.demand import forecast_demand


def history(rates, *, year=2025, month=1, known_availability=True):
    rows = []
    for offset, daily_rate in enumerate(rates):
        month_index = year * 12 + month - 1 + offset
        row_year, row_month = month_index // 12, month_index % 12 + 1
        days = calendar.monthrange(row_year, row_month)[1]
        rows.append(
            {
                "month": date(row_year, row_month, 1).isoformat(),
                "quantity": daily_rate * days,
                "stockout_days": 0 if known_availability else None,
            }
        )
    return rows


def test_explicit_future_seasonality_boosts_forecast():
    rows = history([10] * 6)
    neutral = forecast_demand(rows, "2025-07-01", "2025-08-01")
    seasonal = forecast_demand(rows, "2025-07-01", "2025-08-01", seasonality={7: 1.8})
    assert neutral["forecast_demand"] == pytest.approx(310)
    assert seasonal["forecast_demand"] == pytest.approx(558)
    assert seasonal["seasonal_factor"] == 1.8
    assert seasonal["seasonality_source"] == "explicit"


def test_seasonality_deseasonalizes_history_and_weights_target_days():
    rows = history([20] * 6)
    factors = {month: 2 for month in range(1, 7)} | {7: 3, 8: 1}
    result = forecast_demand(rows, "2025-07-30", "2025-08-03", seasonality=factors)
    assert result["base_daily_demand"] == pytest.approx(10)
    assert result["seasonal_factor"] == pytest.approx(2)
    assert result["forecast_demand"] == pytest.approx(80)


@pytest.mark.parametrize("rates", [[10, 10, 10, 10, 10, 1_000_000], [10, 1_000_000]])
def test_single_spike_cannot_dominate_even_two_month_history(rates):
    rows = history(rates, month=7 - len(rates))
    result = forecast_demand(rows, "2025-07-01", "2025-08-01")
    assert result["forecast_demand"] <= 3 * 310
    assert len(result["anomalies"]) == 1
    anomaly = result["anomalies"][0]
    assert anomaly["month"] == "2025-06-01"
    assert anomaly["original_quantity"] == 30_000_000
    assert anomaly["adjusted_daily_demand"] == 30
    assert result["trend"]["classification"] == "insufficient_data"


def test_forecast_is_deterministic_does_not_mutate_and_is_json_safe():
    rows = history([10, 11, 12, 13, 14, 15], known_availability=False)
    original = copy.deepcopy(rows)
    first = forecast_demand(rows, date(2025, 7, 1), date(2025, 8, 1))
    assert first == forecast_demand(rows, "2025-07-01", "2025-08-01")
    assert rows == original
    assert json.loads(json.dumps(first, allow_nan=False)) == first


@pytest.mark.parametrize(
    ("rates", "classification", "comparison"),
    [([10, 11, 12, 13, 14, 15], "growth", 1), ([15, 14, 13, 12, 11, 10], "decline", -1)],
)
def test_sustained_trend_changes_forecast_with_bounded_adjustment(
    rates, classification, comparison
):
    result = forecast_demand(history(rates), "2025-07-01", "2025-08-01")
    assert result["trend"]["classification"] == classification
    assert (result["trend"]["factor"] - 1) * comparison > 0
    assert 0.75 <= result["trend"]["factor"] <= 1.25
    assert result["trend"]["supporting_steps"] == 5


def test_single_step_change_does_not_establish_sustained_trend():
    result = forecast_demand(history([10, 10, 10, 10, 10, 20]), "2025-07-01", "2025-08-01")
    assert result["trend"]["classification"] == "stable"
    assert result["trend"]["factor"] == 1


def test_growth_adjustment_overrides_estimated_trend():
    rows = history([10, 11, 12, 13, 14, 15])
    result = forecast_demand(rows, "2025-07-01", "2025-08-01", growth_adjustment=0.1)
    assert result["trend"]["classification"] == "growth"
    assert result["trend"]["source"] == "explicit"
    assert result["daily_demand"] == pytest.approx(result["base_daily_demand"] * 1.1)


def test_completely_unavailable_zero_month_is_excluded():
    rows = history([10] * 6)
    rows[-1].update(quantity=0, stockout_days=30)
    result = forecast_demand(rows, "2025-07-01", "2025-08-01")
    assert result["base_daily_demand"] == pytest.approx(10)
    assert "2025-06-01" not in result["used_period"]["months"]
    assert any("весь месяц" in warning for warning in result["warnings"])


def test_known_stockout_days_adjust_exposure_without_fabricated_lost_sales():
    rows = history([10] * 6)
    rows[-1].update(quantity=150, stockout_days=15)
    result = forecast_demand(rows, "2025-07-01", "2025-08-01")
    assert result["base_daily_demand"] == pytest.approx(10)
    assert result["observations"][-1]["exposure_days"] == 15
    assert "lost_sales" not in result
    assert any("lost sales неизвестны" in warning for warning in result["warnings"])


def test_zero_without_availability_stays_observed_zero_and_warns():
    rows = history([10, 10, 10, 10, 10, 0], known_availability=False)
    result = forecast_demand(rows, "2025-07-01", "2025-08-01")
    assert result["base_daily_demand"] == pytest.approx(10 * 15 / 21)
    assert result["observations"][-1]["quantity"] == 0
    assert any("неизвестно, отсутствовал ли товар" in warning for warning in result["warnings"])


def test_future_and_current_months_never_leak_into_forecast():
    rows = history([10] * 6)
    baseline = forecast_demand(rows, "2025-07-15", "2025-08-15")
    rows += history([10_000, 1_000_000], month=7)
    result = forecast_demand(rows, "2025-07-15", "2025-08-15")
    assert result["forecast_demand"] == baseline["forecast_demand"]
    assert result["used_period"]["end"] == "2025-07-01"
    assert len(result["used_period"]["months"]) == 6


def test_missing_months_are_unknown_and_not_filled_with_zeros():
    rows = history([10, 20, 10, 20, 10, 20])
    rows = [rows[0], rows[-1]]
    result = forecast_demand(rows, "2025-07-01", "2025-08-01")
    assert result["base_daily_demand"] == pytest.approx((10 * 1 + 20 * 6) / 7)
    assert len(result["used_period"]["missing_months"]) == 4
    assert result["trend"]["classification"] == "insufficient_data"
    assert any("не заменялись нулём" in warning for warning in result["warnings"])


def test_partial_unknown_and_duplicate_months_are_excluded():
    rows = [
        {"month": "2025-01-15", "quantity": 100},
        {"month": "2025-02-01", "quantity": None},
        {"month": "2025-03-01", "quantity": 100},
        {"month": "2025-03-01", "quantity": 100},
        {"month": "not-a-date", "quantity": 100},
    ]
    result = forecast_demand(rows, "2025-07-01", "2025-08-01")
    assert result["forecast_demand"] is None
    assert result["base_daily_demand"] is None
    assert result["used_period"]["months"] == []
    assert len(result["warnings"]) >= 4


def test_old_history_is_not_silently_substituted_for_recent_missing_months():
    result = forecast_demand(history([10] * 6, year=2020), "2025-07-01", "2025-08-01")
    assert result["forecast_demand"] is None


def test_infers_repeatable_seasonality_only_from_two_complete_years():
    rates = [10] * 24
    rates[6] = rates[18] = 20
    rows = history(rates, year=2023)
    result = forecast_demand(rows, "2025-01-01", "2025-02-01", lookback_months=6)
    assert result["seasonality_source"] == "inferred"
    assert result["seasonality"]["7"] == pytest.approx(result["seasonality"]["1"] * 2)
    assert result["base_daily_demand"] * result["seasonal_factor"] == pytest.approx(10)
    assert result["anomalies"] == []
    short = forecast_demand(rows[1:], "2025-01-01", "2025-02-01")
    assert short["seasonality_source"] == "neutral"
    assert short["seasonal_factor"] == 1


def test_one_huge_historical_sale_cannot_generate_seasonality():
    rates = [10] * 24
    rates[18] = 1_000_000
    result = forecast_demand(history(rates, year=2023), "2025-01-01", "2025-02-01")
    assert result["seasonality_source"] == "neutral"
    assert result["seasonal_factor"] == 1
    assert result["forecast_demand"] < 620
    assert len(result["anomalies"]) == 1


@pytest.mark.parametrize("quantity", [float("nan"), float("inf"), -1, True, "100"])
def test_invalid_quantities_are_not_forecast(quantity):
    result = forecast_demand(
        [{"month": "2025-06-01", "quantity": quantity}], "2025-07-01", "2025-08-01"
    )
    assert result["forecast_demand"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "config",
    [
        {"lookback_months": 0},
        {"lookback_months": True},
        {"spike_multiplier": 1},
        {"trend_min_months": 3},
        {"growth_adjustment": -1.1},
        {"growth_adjustment": float("inf")},
        {"seasonality": {13: 1}},
        {"seasonality": {7: 0}},
    ],
)
def test_invalid_parameters_raise(config):
    with pytest.raises(ValueError):
        forecast_demand(history([10] * 6), "2025-07-01", "2025-08-01", **config)


def test_missing_explicit_seasonality_is_neutral_and_warns():
    result = forecast_demand(history([10] * 6), "2025-07-01", "2025-08-01", seasonality={"7": None})
    assert result["seasonal_factor"] == 1
    assert result["forecast_demand"] == pytest.approx(310)
    assert any("Не задан коэффициент" in warning for warning in result["warnings"])


@pytest.mark.parametrize(
    "config",
    [
        {"growth_adjustment": 5},
        {"seasonality": {7: 1e308}},
        {"seasonality": {6: 1e-308}},
        {"spike_multiplier": 1e308},
    ],
)
def test_extreme_finite_inputs_return_json_safe_evidence(config):
    rows = history([10] * 6)
    for row in rows:
        month = date.fromisoformat(row["month"])
        row["quantity"] = 1e308
        row["stockout_days"] = calendar.monthrange(month.year, month.month)[1] - 1
    result = forecast_demand(rows, "2025-07-01", "2025-08-01", **config)
    json.dumps(result, allow_nan=False)
    assert result["forecast_demand"] is None


def test_tiny_exposure_cannot_produce_infinite_evidence():
    result = forecast_demand(
        [{"month": "2025-06-01", "quantity": 1e308, "stockout_days": 29.999999999999996}],
        "2025-07-01",
        "2025-08-01",
    )
    json.dumps(result, allow_nan=False)
    assert result["forecast_demand"] is None
