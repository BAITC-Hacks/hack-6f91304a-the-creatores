from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

from backend.agent.client import ChatAgent
from backend.config import Settings
from backend.errors import AppError
from backend.models import (
    CalculateRequest,
    Calculation,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    RecommendationsResponse,
    UploadResponse,
    Urgency,
)
from backend.services.body_limit import BodyLimitMiddleware
from backend.services.calculations import CalculationAdapter, CalculationService
from backend.services.export import export_calculation
from backend.services.storage import Storage
from backend.services.uploads import upload_dataset


def create_app(settings=None, adapter=None, ai_client=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        storage = Storage(settings.data_dir)
        provider = adapter or CalculationAdapter(settings)
        service = CalculationService(storage, provider)
        app.state.storage = storage
        app.state.adapter = provider
        app.state.service = service
        app.state.agent = ChatAgent(settings, storage, service, ai_client)
        yield
        await app.state.agent.close()

    app = FastAPI(
        title="ЗакупAI",
        version="0.1.0",
        lifespan=lifespan,
        description="Локальная демонстрация без авторизации. ID не является правом доступа.",
        responses={
            status: {"model": ErrorResponse}
            for status in (400, 404, 409, 413, 422, 500, 502, 503, 504)
        },
    )
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["Content-Disposition"],
    )

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse(exc.body(), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        details = [
            {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
            for item in exc.errors()
        ]
        return JSONResponse(
            AppError(422, "validation_error", "Проверьте поля запроса.", details).body(),
            status_code=422,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(
            AppError(exc.status_code, "http_error", str(exc.detail)).body(),
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return JSONResponse(
            AppError(500, "internal_error", "Внутренняя ошибка сервера.").body(), status_code=500
        )

    @app.get("/api/health", response_model=HealthResponse)
    def health(request: Request):
        return {
            "status": "ok",
            "demo": settings.demo_mode,
            "calculations": {
                "available": request.app.state.adapter.available,
                "provider": request.app.state.adapter.name,
            },
            "ai": {
                "configured": settings.ai_configured,
                "status": "configured_not_checked" if settings.ai_configured else "disabled",
            },
        }

    @app.post(
        "/api/upload",
        response_model=UploadResponse,
        status_code=201,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["files"],
                            "properties": {
                                "files": {
                                    "type": "array",
                                    "items": {"type": "string", "format": "binary"},
                                }
                            },
                        }
                    }
                },
            }
        },
    )
    async def upload(request: Request):
        async with request.form(
            max_files=settings.max_upload_files, max_fields=0, max_part_size=settings.max_file_bytes
        ) as form:
            items = form.multi_items()
            if any(key != "files" or not isinstance(value, UploadFile) for key, value in items):
                raise AppError(422, "invalid_form", "Передайте .xlsx в multipart-поле files.")
            dataset = await upload_dataset(
                form.getlist("files"),
                request.app.state.storage,
                request.app.state.adapter,
                settings,
            )
            return UploadResponse.model_validate(
                dataset.model_dump(exclude={"provider", "payload"})
            )

    @app.post("/api/calculate", response_model=Calculation, status_code=201)
    def calculate(body: CalculateRequest, request: Request):
        return request.app.state.service.calculate(body.dataset_id, body.parameters)

    @app.get("/api/recommendations", response_model=RecommendationsResponse)
    def recommendations(
        request: Request,
        calculation_id: UUID,
        supplier: str | None = None,
        urgency: Urgency | None = None,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ):
        result = request.app.state.service.get(calculation_id)
        rows = [
            r
            for r in result.recommendations
            if (supplier is None or r.supplier == supplier)
            and (urgency is None or r.urgency == urgency)
        ]
        return RecommendationsResponse(
            calculation_id=result.calculation_id,
            dataset_id=result.dataset_id,
            demo=result.demo,
            parameters=result.parameters,
            forecast_start=result.forecast_start,
            forecast_end=result.forecast_end,
            warnings=result.warnings,
            recommendations=rows[offset : offset + limit],
            total=len(rows),
            offset=offset,
            limit=limit,
        )

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest, request: Request):
        return await request.app.state.agent.chat(body)

    @app.get(
        "/api/export",
        response_class=Response,
        responses={
            200: {
                "content": {
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                }
            }
        },
    )
    def export(request: Request, calculation_id: UUID):
        calculation = request.app.state.service.get(calculation_id)
        content = export_calculation(calculation)
        return Response(
            content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="order-{calculation_id}.xlsx"'},
        )

    return app


app = create_app()
