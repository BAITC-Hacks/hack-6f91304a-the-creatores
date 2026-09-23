from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.config import Settings
from backend.main import create_app


def workbook_bytes(value="Uploaded source, not synthetic products"):
    workbook = Workbook()
    workbook.active.append(["sku", "value"])
    workbook.active.append(["000987", value])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def upload(client, value="source"):
    response = client.post(
        "/api/upload",
        files=[
            (
                "files",
                (
                    "sales.xlsx",
                    workbook_bytes(value),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )
        ],
    )
    assert response.status_code == 201, response.text
    return response.json()


def parameters(**changes):
    return {
        "calculation_date": "2026-09-23",
        "supplier": None,
        "lead_time_days": 7,
        "review_period_days": 14,
        "safety_stock_days": 10,
        "demand_growth_adjustment": None,
        **changes,
    }


def calculate(client, dataset_id, **changes):
    response = client.post(
        "/api/calculate", json={"dataset_id": dataset_id, "parameters": parameters(**changes)}
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        demo_mode=True,
        openai_api_key="",
        openai_model="",
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
