"""统一错误格式：{"error": {"code", "message", "fields"?}}，见接口约定 1.4。"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

_HTTP_ERRORS = {
    401: ("UNAUTHORIZED", "请先登录"),
    403: ("FORBIDDEN", "没有权限访问"),
    404: ("NOT_FOUND", "内容不存在或已被删除"),
    405: ("NOT_FOUND", "内容不存在或已被删除"),
}


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict[str, str] | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields


def _response(status: int, code: str, message: str, fields: dict[str, str] | None = None):
    error: dict = {"code": code, "message": message}
    if fields:
        error["fields"] = fields
    return JSONResponse({"error": error}, status_code=status)


def _field_message(err: dict) -> str:
    # 自定义校验器抛出的 ValueError 是写给用户看的中文，其余（缺字段、类型不对）统一提示
    if err["type"] == "value_error":
        return str(err["ctx"]["error"])
    return "格式不正确"


async def _app_error(_: Request, exc: AppError):
    return _response(exc.status, exc.code, exc.message, exc.fields)


async def _validation_error(_: Request, exc: RequestValidationError):
    fields = {}
    for err in exc.errors():
        # loc 形如 ("body", "username") 或判别联合里的 ("body", "student", "grade")
        name = str(err["loc"][-1]) if len(err["loc"]) > 1 else "body"
        fields.setdefault(name, _field_message(err))
    return _response(400, "VALIDATION_ERROR", next(iter(fields.values())), fields)


async def _http_error(_: Request, exc: HTTPException):
    code, message = _HTTP_ERRORS.get(exc.status_code, ("ERROR", "请求失败"))
    return _response(exc.status_code, code, message)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(HTTPException, _http_error)
