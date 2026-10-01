from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.config import get_settings


def _error_response(
    code: str, message: str, details: object, status: int
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def create_app() -> FastAPI:
    application = FastAPI(title="Document Q&A Bot API", version="0.1.0")
    settings = get_settings()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.exception_handler(HTTPException)
    async def http_exception_handler(
        _: Request, exception: HTTPException
    ) -> JSONResponse:
        detail = exception.detail
        if isinstance(detail, dict):
            return _error_response(
                detail.get("code", "HTTP_ERROR"),
                detail.get("message", "Request failed"),
                detail.get("details", {}),
                exception.status_code,
            )
        return _error_response("HTTP_ERROR", str(detail), {}, exception.status_code)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exception: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            "VALIDATION_ERROR", "Request validation failed", exception.errors(), 400
        )

    application.include_router(health_router, prefix="/api")
    application.include_router(documents_router, prefix="/api")
    application.include_router(chat_router, prefix="/api")
    application.include_router(conversations_router, prefix="/api")
    return application


app = create_app()
