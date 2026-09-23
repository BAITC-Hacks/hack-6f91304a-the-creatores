import sys
from types import SimpleNamespace

from conftest import calculate, parameters, upload
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services import demo


def test_external_provider_contract(settings, monkeypatch):
    received = []

    def prepare(paths, sources):
        assert all(path.is_file() for path in paths)
        assert len(sources) == 1
        return {
            "report": {"valid": True, "business_validation": "passed"},
            "payload": {"test_fixture_only": True},
        }

    def compute(payload, params):
        # This is a test double, not a production forecasting implementation.
        received.append(payload)
        result = demo.calculate(payload, params).model_dump()
        result["warnings"] = []
        return result

    settings.demo_mode = False
    settings.calculation_module = "test_calculation_provider"
    monkeypatch.setitem(
        sys.modules,
        settings.calculation_module,
        SimpleNamespace(prepare_dataset=prepare, calculate=compute),
    )
    with TestClient(create_app(settings)) as client:
        dataset = upload(client)
        assert not dataset["demo"]
        assert dataset["validation"]["business_validation"] == "passed"
        result = calculate(client, dataset["dataset_id"])
        assert not result["demo"]
        assert received == [{"test_fixture_only": True}]


def test_provider_cannot_silently_change_parameters(settings):
    from backend.services.calculations import CalculationAdapter

    adapter = CalculationAdapter(settings)

    def compute(payload, params):
        params.lead_time_days = 99
        return demo.calculate(payload, params)

    adapter.module = SimpleNamespace(prepare_dataset=demo.prepare_dataset, calculate=compute)
    with TestClient(create_app(settings, adapter=adapter)) as client:
        dataset = upload(client)
        response = client.post(
            "/api/calculate", json={"dataset_id": dataset["dataset_id"], "parameters": parameters()}
        )
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "provider_error"


def test_provider_invalid_output_is_rejected(settings):
    from backend.services.calculations import CalculationAdapter

    adapter = CalculationAdapter(settings)

    def compute(payload, params):
        result = demo.calculate(payload, params)
        result.recommendations[0].recommended_qty = -1
        return result

    adapter.module = SimpleNamespace(prepare_dataset=demo.prepare_dataset, calculate=compute)
    with TestClient(create_app(settings, adapter=adapter)) as client:
        dataset = upload(client)
        response = client.post(
            "/api/calculate", json={"dataset_id": dataset["dataset_id"], "parameters": parameters()}
        )
        assert response.status_code == 502
