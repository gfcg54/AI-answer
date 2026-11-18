from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.quiz import router as quiz_router
from app.api.v1.routes.report import router as report_router
from app.api.v1.routes.user import router as user_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.database import dispose_database, init_database
from app.models.common import ApiErrorResponse


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().database_url is not None:
        await init_database()
    yield
    await dispose_database()


app = FastAPI(title=get_settings().app_name, version="1.0.0", lifespan=lifespan)
api_router = APIRouter(prefix="/api/v1")


@app.exception_handler(AppError)
async def app_error_handler(
    request: Request,
    error: AppError,
) -> JSONResponse:
    body = ApiErrorResponse(code=error.code, message=error.message)
    return JSONResponse(
        status_code=error.status_code,
        content=body.model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    body = ApiErrorResponse(
        code=4000,
        message="请求参数无效，请检查输入内容。",
    )
    return JSONResponse(status_code=422, content=body.model_dump())


api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(quiz_router)
api_router.include_router(report_router)
api_router.include_router(user_router)
app.include_router(api_router)
