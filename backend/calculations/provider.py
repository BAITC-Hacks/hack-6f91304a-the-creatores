"""Adapter for participant #3's existing provider contract, without model changes."""

from datetime import timedelta

from backend.calculations.excel_loader import load_workbooks
from backend.calculations.orders import calculate_order
from backend.calculations.validation import validate_dataset
from backend.models import CalculationParameters, PreparedDataset, ProviderResult


def prepare_dataset(files, sources=None):
    """Read workbook business data and return a JSON-safe validated dataset."""
    return PreparedDataset.model_validate(load_workbooks(files, sources))


def calculate_detailed(payload, parameters, *, forecast_options=None):
    """Pure calculation with per-SKU evidence; no storage, IDs, or API calls.

    ``recommendations`` includes an ``explanation`` field. This richer result is
    for direct use; the current backend model accepts ``calculate()`` instead.
    """
    if payload.get("schema_version") != 1:
        raise ValueError("Неизвестная версия данных; загрузите Excel повторно.")
    report = validate_dataset(payload)
    if not report["valid"]:
        raise ValueError("; ".join(report["errors"]))
    params = CalculationParameters.model_validate(parameters)
    recommendations = [
        calculate_order(product, params, forecast_options=forecast_options)
        for product in sorted(payload["products"], key=lambda item: (item["supplier"], item["sku"]))
        if params.supplier is None or product["supplier"] == params.supplier
    ]
    warnings = list(report["warnings"])
    if not recommendations:
        warnings.append("Для выбранного поставщика нет товаров в наборе данных.")
    return {
        "forecast_start": params.calculation_date.isoformat(),
        "forecast_end": (
            params.calculation_date
            + timedelta(days=params.lead_time_days + params.review_period_days)
        ).isoformat(),
        "recommendations": recommendations,
        "warnings": list(dict.fromkeys(warnings)),
    }


def calculate(payload, parameters):
    """Return the strict backend contract; detailed evidence is available separately."""
    result = calculate_detailed(payload, parameters)
    result["recommendations"] = [
        {key: value for key, value in row.items() if key != "explanation"}
        for row in result["recommendations"]
    ]
    for row in result["recommendations"]:
        if len(row["warnings"]) > 100:
            omitted = len(row["warnings"]) - 99
            row["warnings"] = row["warnings"][:99] + [
                f"Ещё предупреждений: {omitted}; показаны первые 99 записей."
            ]
    return ProviderResult.model_validate(result)
