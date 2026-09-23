from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, max_length=500, strict=True)]
Quantity = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]
Days = Annotated[int, Field(ge=0, le=3650, strict=True)]
Urgency = Literal["high", "medium", "low", "none", "unknown"]


class Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, revalidate_instances="always"
    )


class ErrorBody(Model):
    code: str
    message: str
    details: list[Any]


class ErrorResponse(Model):
    error: ErrorBody


class CalculationHealth(Model):
    available: bool
    provider: str


class AIHealth(Model):
    configured: bool
    status: Literal["configured_not_checked", "disabled"]


class HealthResponse(Model):
    status: Literal["ok"]
    demo: bool
    calculations: CalculationHealth
    ai: AIHealth


class CalculationParameters(Model):
    calculation_date: date
    supplier: Text | None = None  # null = all suppliers, not an invented supplier
    lead_time_days: Days
    review_period_days: Annotated[int, Field(ge=1, le=3650, strict=True)]
    safety_stock_days: Days
    demand_growth_adjustment: (
        Annotated[float, Field(ge=-1, le=5, allow_inf_nan=False, strict=True)] | None
    ) = None


class Recommendation(Model):
    sku: Text
    name: Text
    supplier: Text
    unit: Text | None
    stock: Quantity | None
    incoming_in_period: Quantity | None
    forecast_demand: Quantity | None
    safety_stock: Quantity | None
    moq: Quantity | None
    order_multiple: Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)] | None
    recommended_qty: Quantity | None
    urgency: Urgency
    reason: Annotated[str, Field(min_length=1, max_length=4000)]
    warnings: list[str] = Field(default_factory=list, max_length=100)


class Source(Model):
    file_id: UUID
    filename: Text
    size_bytes: int
    sha256: str
    sheets: list[str]


class ValidationReport(Model):
    valid: bool
    business_validation: Literal["passed", "failed", "not_performed"]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_status(self):
        if self.valid and (self.errors or self.business_validation == "failed"):
            raise ValueError("A valid dataset cannot contain validation errors")
        return self


class PreparedDataset(Model):
    """Provider result; payload stays on the server and is never sent to the LLM."""

    report: ValidationReport
    payload: dict[str, Any]


class UploadResponse(Model):
    dataset_id: UUID
    created_at: datetime
    demo: bool
    sources: list[Source]
    validation: ValidationReport


class Dataset(UploadResponse):
    provider: str
    payload: dict[str, Any]


class ProviderResult(Model):
    recommendations: list[Recommendation]
    forecast_start: date
    forecast_end: date  # exclusive
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_period(self):
        if self.forecast_end <= self.forecast_start:
            raise ValueError("forecast_end must be after forecast_start (exclusive)")
        keys = [(row.supplier, row.sku) for row in self.recommendations]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate supplier/sku in recommendations")
        return self


class CalculateRequest(Model):
    dataset_id: UUID
    parameters: CalculationParameters


class Calculation(ProviderResult):
    calculation_id: UUID
    dataset_id: UUID
    created_at: datetime
    demo: bool
    provider: str
    parameters: CalculationParameters
    sources: list[Source]


class RecommendationsResponse(Model):
    calculation_id: UUID
    dataset_id: UUID
    demo: bool
    parameters: CalculationParameters
    forecast_start: date
    forecast_end: date
    warnings: list[str]
    recommendations: list[Recommendation]
    total: int
    offset: int
    limit: int


class ChatRequest(Model):
    dataset_id: UUID
    calculation_id: UUID | None = None
    conversation_id: UUID | None = None
    message: Annotated[str, Field(min_length=1, max_length=4000)]


class ToolEvidence(Model):
    tool: str
    result: dict[str, Any]


class ChatResponse(Model):
    conversation_id: UUID
    dataset_id: UUID
    calculation_id: UUID | None
    ai_available: bool
    demo: bool
    message: str
    applied_parameters: CalculationParameters | None
    export_url: str | None
    evidence: list[ToolEvidence] = Field(default_factory=list)


class Conversation(Model):
    conversation_id: UUID
    dataset_id: UUID
    calculation_id: UUID | None = None
    messages: list[dict[str, str]] = Field(default_factory=list)
