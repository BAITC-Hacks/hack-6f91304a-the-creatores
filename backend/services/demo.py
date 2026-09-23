"""Synthetic integration fixture, NOT a forecasting model or Excel business parser."""

from datetime import timedelta
from math import ceil

from backend.models import PreparedDataset, ProviderResult, Recommendation, ValidationReport

DEMO_WARNING = (
    "ДЕМО: синтетические товары и спрос; содержимое загруженных Excel не участвует в расчёте."
)


def prepare_dataset(files, sources):
    return PreparedDataset(
        report=ValidationReport(
            valid=True,
            business_validation="not_performed",
            warnings=[DEMO_WARNING],
            summary={"uploaded_files": len(sources), "synthetic_products": 2},
        ),
        payload={"fixture": "demo-v1"},
    )


def calculate(payload, parameters):
    period = parameters.lead_time_days + parameters.review_period_days
    growth = 1 + (parameters.demand_growth_adjustment or 0)
    rows = []
    for sku, supplier, daily, stock, incoming, moq, multiple in [
        ("000123", "ИЭК", 2, 10, 5, 12, 6),
        ("000456", "SystemElectric", 1, 8, 0, 5, 1),
    ]:
        if parameters.supplier and parameters.supplier != supplier:
            continue
        demand = daily * growth * period
        safety = daily * growth * parameters.safety_stock_days
        need = max(0, demand + safety - stock - incoming)
        order = ceil(max(need, moq) / multiple) * multiple if need > 0 else 0
        rows.append(
            Recommendation(
                sku=sku,
                name="Демонстрационный товар",
                supplier=supplier,
                unit="шт",
                stock=stock,
                incoming_in_period=incoming,
                forecast_demand=demand,
                safety_stock=safety,
                moq=moq,
                order_multiple=multiple,
                recommended_qty=order,
                urgency="high" if order else "none",
                reason=(
                    f"ДЕМО: спрос {demand:g} + запас {safety:g} − остаток {stock} "
                    f"− поставки {incoming}; положительная потребность округлена до MOQ "
                    f"и кратности. Синтетический спрос {daily:g} шт/день."
                ),
                warnings=[DEMO_WARNING],
            )
        )
    return ProviderResult(
        recommendations=rows,
        forecast_start=parameters.calculation_date,
        forecast_end=parameters.calculation_date + timedelta(days=period),
        warnings=[DEMO_WARNING],
    )
