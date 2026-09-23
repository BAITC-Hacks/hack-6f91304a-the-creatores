import json
from typing import Annotated

from pydantic import Field, ValidationError

from backend.errors import AppError
from backend.models import CalculationParameters, Model, Text, Urgency


class EmptyArgs(Model):
    pass


class FilterArgs(Model):
    supplier: Text | None = None
    urgency: Urgency | None = None
    offset: Annotated[int, Field(ge=0, strict=True)] = 0
    limit: Annotated[int, Field(ge=1, le=50, strict=True)] = 20


class ExplainArgs(Model):
    sku: Text
    supplier: Text | None = None


TOOL_MODELS = {
    "get_data_quality": (EmptyArgs, "Получить качество и агрегированный состав текущего набора."),
    "run_calculation": (
        CalculationParameters,
        "Создать НОВЫЙ расчёт. Все обязательные параметры запроси у пользователя; "
        "при пересчёте можно сохранить параметры текущего расчёта.",
    ),
    "get_recommendations": (FilterArgs, "Получить страницу фактических рекомендаций и параметры."),
    "explain_sku": (ExplainArgs, "Получить фактический расчёт конкретной позиции по артикулу."),
    "get_export_link": (EmptyArgs, "Получить ссылку на Excel текущего расчёта."),
}


def strict_schema(schema):
    """Responses strict mode requires every property, with nullable optional values."""
    if isinstance(schema, dict):
        schema.pop("default", None)
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
            schema["required"] = list(schema.get("properties", {}))
        for value in schema.values():
            strict_schema(value)
    elif isinstance(schema, list):
        for value in schema:
            strict_schema(value)
    return schema


def tool_definitions():
    return [
        {
            "type": "function",
            "name": name,
            "description": description,
            "strict": True,
            "parameters": strict_schema(model.model_json_schema()),
        }
        for name, (model, description) in TOOL_MODELS.items()
    ]


def validation_details(exc):
    # Do not echo inputs (potential secrets/table content) in error responses.
    return [
        {"field": ".".join(map(str, err["loc"])), "message": err["msg"]}
        for err in exc.errors(include_input=False, include_context=False, include_url=False)
    ]


class ToolContext:
    """Dataset and calculation IDs are server-bound, never accepted from tool arguments."""

    def __init__(self, service, dataset_id, calculation_id, on_calculation=None):
        self.service = service
        self.dataset_id = dataset_id
        self.calculation_id = calculation_id
        self.on_calculation = on_calculation

    def current(self):
        if not self.calculation_id:
            raise AppError(
                422, "calculation_required", "Сначала задайте параметры и выполните расчёт."
            )
        return self.service.get(self.calculation_id, self.dataset_id)

    def metadata(self, calculation):
        return {
            "calculation_id": str(calculation.calculation_id),
            "demo": calculation.demo,
            "parameters": calculation.parameters.model_dump(mode="json"),
            "forecast_start": str(calculation.forecast_start),
            "forecast_end_exclusive": str(calculation.forecast_end),
            "warnings": calculation.warnings,
        }

    def execute(self, name, arguments):
        if name not in TOOL_MODELS:
            raise AppError(422, "unknown_tool", "Инструмент не разрешён.")
        if len(arguments) > 16000:
            raise AppError(422, "invalid_tool_arguments", "Аргументы инструмента слишком велики.")
        try:
            args = TOOL_MODELS[name][0].model_validate_json(arguments)
        except ValidationError as exc:
            raise AppError(
                422,
                "invalid_tool_arguments",
                "Проверьте параметры инструмента.",
                validation_details(exc),
            ) from exc
        if name == "get_data_quality":
            dataset = self.service.dataset(self.dataset_id)
            # Provider payload, filenames and arbitrary summary are deliberately not shared.
            return {
                "demo": dataset.demo,
                "valid": dataset.validation.valid,
                "business_validation": dataset.validation.business_validation,
                "file_count": len(dataset.sources),
                "sheet_count": sum(len(s.sheets) for s in dataset.sources),
                "errors": dataset.validation.errors[:20],
                "warnings": dataset.validation.warnings[:20],
            }
        if name == "run_calculation":
            result = self.service.calculate(self.dataset_id, args)
            self.calculation_id = result.calculation_id
            if self.on_calculation:
                self.on_calculation(result.calculation_id)
            return {
                **self.metadata(result),
                "positions": len(result.recommendations),
                "high_urgency_positions": sum(r.urgency == "high" for r in result.recommendations),
            }
        calculation = self.current()
        if name == "get_export_link":
            return {
                **self.metadata(calculation),
                "export_url": f"/api/export?calculation_id={calculation.calculation_id}",
            }
        if name == "explain_sku":
            rows = [
                r
                for r in calculation.recommendations
                if r.sku == args.sku and (args.supplier is None or r.supplier == args.supplier)
            ]
            if not rows:
                raise AppError(404, "sku_not_found", "Артикул не найден в этом расчёте.")
            if len(rows) > 1:
                raise AppError(422, "supplier_required", "Уточните поставщика этого артикула.")
            return {**self.metadata(calculation), "recommendation": rows[0].model_dump(mode="json")}
        rows = [
            r
            for r in calculation.recommendations
            if (args.supplier is None or r.supplier == args.supplier)
            and (args.urgency is None or r.urgency == args.urgency)
        ]
        return {
            **self.metadata(calculation),
            "total": len(rows),
            "offset": args.offset,
            "recommendations": [
                r.model_dump(mode="json") for r in rows[args.offset : args.offset + args.limit]
            ],
        }


def tool_output(result):
    return json.dumps(result, ensure_ascii=False, allow_nan=False)
