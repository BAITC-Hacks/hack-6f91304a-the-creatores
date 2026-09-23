"""Run from repository root: python -m contracts.generate. Does not need an API key."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from backend.main import app
from backend.models import Calculation, CalculationParameters
from backend.services.demo import calculate


def main():
    root = Path(__file__).parent
    parameters = CalculationParameters(
        calculation_date="2026-09-23",
        supplier=None,
        lead_time_days=7,
        review_period_days=14,
        safety_stock_days=10,
        demand_growth_adjustment=None,
    )
    result = calculate({"fixture": "demo-v1"}, parameters)
    example = Calculation(
        **result.model_dump(),
        calculation_id=UUID("22222222-2222-4222-8222-222222222222"),
        dataset_id=UUID("11111111-1111-4111-8111-111111111111"),
        created_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        demo=True,
        provider="demo-v1",
        parameters=parameters,
        sources=[],
    )
    (root / "recommendation.example.json").write_text(
        example.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (root / "openapi.json").write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
