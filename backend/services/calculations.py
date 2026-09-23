import importlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.errors import AppError
from backend.models import Calculation, Dataset, PreparedDataset, ProviderResult
from backend.services import demo


class CalculationAdapter:
    def __init__(self, settings):
        self.demo = settings.demo_mode
        self.name = "demo-v1" if self.demo else settings.calculation_module
        self.module = None
        try:
            self.module = demo if self.demo else importlib.import_module(self.name)
            if not all(
                callable(getattr(self.module, name, None))
                for name in ("prepare_dataset", "calculate")
            ):
                self.module = None
        except Exception:
            # Never substitute a demo module when an import/dependency fails.
            self.module = None

    @property
    def available(self):
        return self.module is not None

    def require(self):
        if not self.available:
            raise AppError(
                503,
                "calculation_unavailable",
                "Расчётный модуль не подключён. Подключите модуль участника №2 "
                "или явно включите DEMO_MODE для синтетической демонстрации.",
            )

    def prepare(self, paths, sources):
        self.require()
        try:
            result = PreparedDataset.model_validate(self.module.prepare_dataset(paths, sources))
            # Reject non-JSON payloads and NaN before writing a persistent dataset.
            json.dumps(result.model_dump(mode="python"), allow_nan=False)
            if not self.demo and result.report.business_validation == "not_performed":
                raise ValueError("Business validation is required in real mode")
            return result
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                502, "provider_error", "Расчётный модуль не смог проверить данные по контракту."
            ) from exc

    def calculate(self, dataset, parameters):
        self.require()
        if dataset.provider != self.name or dataset.demo != self.demo:
            raise AppError(
                409,
                "provider_changed",
                "Режим или провайдер изменён. Загрузите набор данных заново.",
            )
        if not dataset.validation.valid or dataset.validation.errors:
            raise AppError(
                422,
                "dataset_invalid",
                "Исправьте ошибки загруженных данных.",
                dataset.validation.errors,
            )
        try:
            result = ProviderResult.model_validate(
                self.module.calculate(dataset.payload, parameters.model_copy(deep=True))
            )
            expected_end = parameters.calculation_date + timedelta(
                days=parameters.lead_time_days + parameters.review_period_days
            )
            if result.forecast_start != parameters.calculation_date:
                raise ValueError("Unexpected forecast start")
            if result.forecast_end != expected_end:
                raise ValueError("Unexpected forecast end")
            if parameters.supplier and any(
                r.supplier != parameters.supplier for r in result.recommendations
            ):
                raise ValueError("Supplier filter was not applied")
            return result
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                502,
                "provider_error",
                "Расчётный модуль вернул результат, не соответствующий контракту.",
            ) from exc


class CalculationService:
    def __init__(self, storage, adapter):
        self.storage = storage
        self.adapter = adapter

    def dataset(self, dataset_id):
        return self.storage.get("dataset", dataset_id, Dataset)

    def get(self, calculation_id, dataset_id=None):
        result = self.storage.get("calculation", calculation_id, Calculation)
        if dataset_id is not None and result.dataset_id != dataset_id:
            raise AppError(409, "dataset_mismatch", "Расчёт относится к другому набору данных.")
        return result

    def calculate(self, dataset_id, parameters):
        dataset = self.dataset(dataset_id)
        result = self.adapter.calculate(dataset, parameters)
        warnings = list(dict.fromkeys(dataset.validation.warnings + result.warnings))
        calculation = Calculation(
            **result.model_dump(exclude={"warnings"}),
            warnings=warnings,
            calculation_id=uuid4(),
            dataset_id=dataset_id,
            created_at=datetime.now(timezone.utc),
            demo=dataset.demo,
            provider=dataset.provider,
            parameters=parameters,
            sources=dataset.sources,
        )
        self.storage.create("calculation", calculation.calculation_id, calculation)
        return calculation
