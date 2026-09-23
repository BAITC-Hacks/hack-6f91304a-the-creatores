import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from conftest import calculate, parameters, upload
from fastapi.testclient import TestClient
from openai import APIConnectionError, APITimeoutError

from backend.agent.tools import ToolContext, tool_definitions
from backend.errors import AppError
from backend.main import create_app


def call(name, arguments):
    return SimpleNamespace(
        type="function_call", name=name, arguments=json.dumps(arguments), call_id="call_" + name
    )


def response(*calls, text="Готово.", status="completed"):
    return SimpleNamespace(output=list(calls), output_text=text, status=status)


def mock_client(*responses):
    return SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=responses)), close=AsyncMock()
    )


def test_tool_arguments_and_scope(client):
    a, b = upload(client), upload(client)
    calculation = calculate(client, a["dataset_id"])
    context = ToolContext(
        client.app.state.service, UUID(a["dataset_id"]), UUID(calculation["calculation_id"])
    )
    for name, arguments in [
        ("shell", {}),
        ("run_calculation", {"lead_time_days": -1}),
        ("get_data_quality", {"dataset_id": b["dataset_id"]}),
        ("get_recommendations", {"limit": 99999}),
    ]:
        with pytest.raises(AppError):
            context.execute(name, json.dumps(arguments))
    with pytest.raises(AppError):
        context.execute("run_calculation", "not json")
    result = context.execute("explain_sku", '{"sku":"000123"}')
    assert result["recommendation"] == calculation["recommendations"][0]
    assert context.execute("get_export_link", "{}")["export_url"].endswith(
        calculation["calculation_id"]
    )


def test_responses_loop_recalculation_and_conversation(settings):
    changed = parameters(supplier="ИЭК", safety_stock_days=20)
    ai = mock_client(
        response(call("run_calculation", changed)),
        response(call("explain_sku", {"sku": "000123", "supplier": "ИЭК"})),
        response(text="Расчёт готов. Страховой запас 20 дней."),
        response(call("get_export_link", {})),
        response(),
    )
    with TestClient(create_app(settings, ai_client=ai)) as client:
        dataset = upload(client)
        old = calculate(client, dataset["dataset_id"])
        reply = client.post(
            "/api/chat",
            json={
                "dataset_id": dataset["dataset_id"],
                "calculation_id": old["calculation_id"],
                "message": "Поставь запас 20 дней",
            },
        )
        assert reply.status_code == 200, reply.text
        body = reply.json()
        assert body["ai_available"] and body["demo"]
        assert body["calculation_id"] != old["calculation_id"]
        assert body["applied_parameters"] == changed
        assert len(body["evidence"]) == 2
        assert client.get(body["export_url"]).status_code == 200
        second = client.post(
            "/api/chat",
            json={
                "dataset_id": dataset["dataset_id"],
                "conversation_id": body["conversation_id"],
                "message": "Ссылка?",
            },
        ).json()
        assert second["calculation_id"] == body["calculation_id"]
        assert second["conversation_id"] == body["conversation_id"]
        assert ai.responses.create.call_args_list[0].kwargs["store"] is False
        sent = ai.responses.create.call_args_list[1].kwargs["input"]
        assert any(
            isinstance(item, dict) and item.get("type") == "function_call_output" for item in sent
        )
        assert not any("Uploaded source" in str(item) for item in sent)
    ai.close.assert_awaited_once()


def test_bad_tool_is_reported_to_model(settings):
    ai = mock_client(
        response(call("run_calculation", {"lead_time_days": -5})),
        response(text="Уточните дату расчёта и сроки поставки."),
    )
    with TestClient(create_app(settings, ai_client=ai)) as client:
        dataset = upload(client)
        reply = client.post(
            "/api/chat", json={"dataset_id": dataset["dataset_id"], "message": "Рассчитай"}
        )
        assert reply.status_code == 200
        assert reply.json()["calculation_id"] is None
        assert reply.json()["evidence"][0]["result"]["error"]["code"] == "invalid_tool_arguments"


def test_tool_limit(settings):
    settings.max_tool_calls = 1
    ai = mock_client(response(call("get_data_quality", {})), response(call("get_data_quality", {})))
    with TestClient(create_app(settings, ai_client=ai)) as client:
        dataset = upload(client)
        reply = client.post(
            "/api/chat", json={"dataset_id": dataset["dataset_id"], "message": "Ещё"}
        )
        assert reply.status_code == 422
        assert reply.json()["error"]["code"] == "tool_limit"
        assert ai.responses.create.await_count == 2


@pytest.mark.parametrize(
    "exception,status",
    [
        (APITimeoutError(request=httpx.Request("POST", "https://api.openai.com")), 504),
        (APIConnectionError(request=httpx.Request("POST", "https://api.openai.com")), 502),
    ],
)
def test_api_errors(settings, exception, status):
    ai = mock_client(exception)
    with TestClient(create_app(settings, ai_client=ai)) as client:
        dataset = upload(client)
        reply = client.post(
            "/api/chat", json={"dataset_id": dataset["dataset_id"], "message": "Чат"}
        )
        assert reply.status_code == status
        assert reply.json()["error"]["details"][0]["conversation_id"]
        assert client.get("/api/health").status_code == 200


def test_total_timeout(settings):
    settings.chat_timeout_seconds = 0.01

    async def delayed(**kwargs):
        await asyncio.sleep(1)
        return response()

    ai = mock_client()
    ai.responses.create.side_effect = delayed
    with TestClient(create_app(settings, ai_client=ai)) as client:
        dataset = upload(client)
        reply = client.post(
            "/api/chat", json={"dataset_id": dataset["dataset_id"], "message": "Чат"}
        )
        assert reply.status_code == 504


def test_unverified_numbers_are_not_presented(settings):
    ai = mock_client(response(text="Закажите 999999 единиц."))
    with TestClient(create_app(settings, ai_client=ai)) as client:
        dataset = upload(client)
        reply = client.post(
            "/api/chat", json={"dataset_id": dataset["dataset_id"], "message": "Заказ"}
        )
        assert "999999" not in reply.json()["message"]
        assert "не подтверждены" in reply.json()["message"]


def test_conversation_lease(client):
    dataset = upload(client)
    body = {"dataset_id": dataset["dataset_id"], "message": "Чат"}
    conversation = client.post("/api/chat", json=body).json()["conversation_id"]
    with client.app.state.storage.conversation_lease(UUID(conversation), 60):
        reply = client.post("/api/chat", json={**body, "conversation_id": conversation})
        assert reply.status_code == 409


def test_strict_tool_schemas():
    for definition in tool_definitions():
        assert definition["strict"] is True
        schema = definition["parameters"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
