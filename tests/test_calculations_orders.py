"""Business behavior tests on synthetic data; no company workbooks are committed."""

import json
from calendar import monthrange
from copy import deepcopy
from decimal import Decimal
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.calculations.orders import calculate_order, round_order_qty
from backend.calculations.provider import calculate, calculate_detailed, prepare_dataset
from backend.main import create_app
from backend.models import CalculationParameters, ProviderResult


def params(**changes):
    return CalculationParameters.model_validate(
        {
            "calculation_date": "2026-09-01",
            "lead_time_days": 10,
            "review_period_days": 20,
            "safety_stock_days": 5,
            **changes,
        }
    )


def product(**changes):
    return {
        "sku": "000123",
        "name": "Тестовый товар",
        "supplier": "ИЭК",
        "unit": "шт",
        "stock": 20.0,
        "moq": 0.0,
        "order_multiple": 1.0,
        "lead_time_days": 10,
        "sales": [
            {
                "month": f"2026-{month:02d}-01",
                "quantity": 2.0 * monthrange(2026, month)[1],
                "stockout_days": 0,
            }
            for month in range(3, 9)
        ],
        "incoming": [{"date": None, "quantity": 0.0}],
        "incoming_known": True,
        "seasonality": {},
        "warnings": [],
        **changes,
    }


def test_order_arithmetic_and_more_incoming_reduces_order():
    initial = calculate_order(product(), params())
    extra = calculate_order(product(incoming=[{"date": "2026-09-10", "quantity": 15}]), params())
    assert initial["forecast_demand"] == pytest.approx(60)
    assert initial["safety_stock"] == pytest.approx(10)
    assert initial["recommended_qty"] == pytest.approx(50)
    assert extra["recommended_qty"] == pytest.approx(35)
    assert extra["recommended_qty"] < initial["recommended_qty"]


def test_high_stock_and_negative_need_produce_zero_even_with_moq():
    result = calculate_order(product(stock=1000, moq=100), params())
    assert result["explanation"]["raw_need"] < 0
    assert result["recommended_qty"] == 0
    assert result["urgency"] == "none"
    assert round_order_qty(-20, moq=100, order_multiple=12) == 0


@pytest.mark.parametrize(
    "need,moq,multiple,expected",
    [
        (1, 25, 12, 36),
        (25, 0, 12, 36),
        (0, 25, 12, 0),
        (0.3, None, 0.1, 0.3),
        (0.31, 0, 0.1, 0.4),
        (2.25, None, None, 2.25),
    ],
)
def test_moq_and_multiple_are_separate_constraints(need, moq, multiple, expected):
    assert round_order_qty(need, moq, multiple) == expected


@pytest.mark.parametrize("kwargs", [{"moq": -1}, {"order_multiple": 0}, {"need": float("nan")}])
def test_invalid_constraints_rejected(kwargs):
    with pytest.raises(ValueError):
        round_order_qty(**{"need": 5, **kwargs})


def test_incoming_interval_includes_start_excludes_end_and_overdue():
    result = calculate_order(
        product(
            incoming=[
                {"date": "2026-08-31", "quantity": 1000},
                {"date": "2026-09-01", "quantity": 3},
                {"date": "2026-09-30", "quantity": 7},
                {"date": "2026-10-01", "quantity": 1000},
            ]
        ),
        params(),
    )
    assert result["incoming_in_period"] == 10
    assert len(result["explanation"]["counted_shipments"]) == 2
    assert any("просрочена" in warning for warning in result["warnings"])


@pytest.mark.parametrize(
    "changes,unknown",
    [
        ({"stock": None}, "stock"),
        ({"incoming": [], "incoming_known": False}, "incoming_in_period"),
        ({"incoming": [{"date": None, "quantity": 100}]}, "incoming_in_period"),
        ({"sales": []}, "forecast_demand"),
    ],
)
def test_missing_critical_values_warn_and_never_invent_order(changes, unknown):
    result = calculate_order(product(**changes), params())
    assert result[unknown] is None
    assert result["recommended_qty"] is None
    assert result["urgency"] == "unknown"
    assert result["warnings"]


def test_missing_optional_constraints_warn_without_hardcoded_moq():
    result = calculate_order(product(moq=None, order_multiple=None, lead_time_days=None), params())
    assert result["recommended_qty"] == pytest.approx(50)
    assert result["moq"] is None
    assert any("MOQ" in warning for warning in result["warnings"])
    assert any("срока поставки" in warning for warning in result["warnings"])


def test_explicit_lead_override_is_explained_and_affects_horizon():
    result = calculate_order(product(lead_time_days=30), params(lead_time_days=20))
    assert result["forecast_demand"] == pytest.approx(80)
    assert result["explanation"]["effective_lead_time_days"] == 20
    assert result["explanation"]["source_lead_time_days"] == 30
    assert any("переопределён" in warning for warning in result["warnings"])


def test_urgency_accounts_for_arrival_timing_even_when_total_order_is_zero():
    late = calculate_order(
        product(stock=0, incoming=[{"date": "2026-09-20", "quantity": 100}]), params()
    )
    early = calculate_order(
        product(stock=0, incoming=[{"date": "2026-09-01", "quantity": 100}]), params()
    )
    assert late["recommended_qty"] == early["recommended_qty"] == 0
    assert late["urgency"] == "high"
    assert early["urgency"] == "none"


def test_detailed_and_compatibility_contracts_deterministic_and_do_not_mutate():
    payload = {"schema_version": 1, "products": [product()]}
    original = deepcopy(payload)
    parameters = params()
    result = calculate_detailed(payload, parameters)
    assert result == calculate_detailed(payload, parameters)
    assert payload == original
    assert parameters == params()
    json.dumps(result, allow_nan=False)
    strict = calculate(payload, parameters)
    assert isinstance(strict, ProviderResult)
    assert (
        strict.recommendations[0].recommended_qty == result["recommendations"][0]["recommended_qty"]
    )
    assert "explanation" not in strict.recommendations[0].model_dump()
    assert result["recommendations"][0]["explanation"]["forecast"]["used_period"]


def test_supplier_filter_and_payload_version():
    payload = {"schema_version": 1, "products": [product()]}
    assert calculate(payload, params(supplier="Другой")).recommendations == []
    with pytest.raises(ValueError, match="версия"):
        calculate({**payload, "schema_version": 2}, params())


def synthetic_workbook():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Товары"
    sheet.append(
        [
            "sku",
            "name",
            "supplier",
            "unit",
            "stock",
            "moq",
            "order_multiple",
            "lead_time_days",
            "incoming",
            "arrival_date",
            "2026-03",
            "2026-04",
            "2026-05",
            "2026-06",
            "2026-07",
            "2026-08",
        ]
    )
    sheet.append(
        ["000123", "Тестовый товар", "ИЭК", "шт", 20, 25, 12, 10, 0, None, 62, 60, 62, 60, 62, 62]
    )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_real_provider_upload_calculate_and_reload(settings):
    settings.demo_mode = False
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json()["calculations"]["available"]
        upload = client.post("/api/upload", files={"files": ("test.xlsx", synthetic_workbook())})
        assert upload.status_code == 201, upload.text
        dataset = upload.json()
        assert dataset["validation"]["valid"], dataset
        response = client.post(
            "/api/calculate",
            json={
                "dataset_id": dataset["dataset_id"],
                "parameters": params().model_dump(mode="json"),
            },
        )
        assert response.status_code == 201, response.text
        result = response.json()
        assert result["recommendations"][0]["sku"] == "000123"
        assert result["recommendations"][0]["recommended_qty"] == 60
        assert result["demo"] is False
    with TestClient(create_app(settings)) as client:
        page = client.get(
            "/api/recommendations", params={"calculation_id": result["calculation_id"]}
        )
        assert page.status_code == 200
        assert page.json()["recommendations"] == result["recommendations"]


def test_prepare_dataset_roundtrip_json(tmp_path):
    path = tmp_path / "test.xlsx"
    path.write_bytes(synthetic_workbook())
    prepared = prepare_dataset([path])
    assert prepared.report.valid, prepared.report.errors
    payload = json.loads(json.dumps(prepared.payload, allow_nan=False))
    assert calculate(payload, params()).recommendations[0].recommended_qty == 60


def test_float_noise_does_not_add_a_whole_package():
    item = product(stock=0.5)
    for sale in item["sales"]:
        month = int(sale["month"][5:7])
        sale["quantity"] = float(Decimal("0.3") * monthrange(2026, month)[1])
    result = calculate_order(item, params())
    assert result["recommended_qty"] == 10
    assert round_order_qty(0.1 + 0.2, None, 0.1) == 0.3
    assert round_order_qty(1e-15, None, 1) == 1
    assert round_order_qty(10, 10.000001, 1) == 11


def test_no_order_still_reports_shortage_after_lead_before_existing_receipt():
    result = calculate_order(
        product(stock=20, incoming=[{"date": "2026-09-20", "quantity": 100}]), params()
    )
    assert result["recommended_qty"] == 0
    assert result["urgency"] == "high"
    assert any("временный дефицит" in warning for warning in result["warnings"])


def test_many_warnings_keep_strict_contract_and_full_details():
    payload = {
        "schema_version": 1,
        "products": [product(warnings=[f"Проверить строку {index}" for index in range(120)])],
    }
    detailed = calculate_detailed(payload, params())
    strict = calculate(payload, params())
    assert len(strict.recommendations[0].warnings) == 100
    assert len(detailed["recommendations"][0]["warnings"]) > 120
    assert "Ещё предупреждений" in strict.recommendations[0].warnings[-1]


def test_extreme_incoming_sum_returns_unknown_finite_json():
    result = calculate_order(
        product(
            incoming=[
                {"date": "2026-09-10", "quantity": 1e308},
                {"date": "2026-09-11", "quantity": 1e308},
            ]
        ),
        params(),
    )
    assert result["recommended_qty"] is None
    assert result["incoming_in_period"] is None
    json.dumps(result, allow_nan=False)
