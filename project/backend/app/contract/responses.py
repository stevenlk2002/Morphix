from fastapi.responses import JSONResponse

from app.contract.envelope import ApiEnvelope, ApiError, ErrorObject, new_request_id


def ok(data=None, status_code: int = 200, request_id: str | None = None) -> JSONResponse:
    """Wrap a DTO (or None) in the unified SuccessEnvelope and return it."""
    env = ApiEnvelope(
        request_id=request_id or new_request_id(),
        success=True,
        data=data,
        error=None,
    )
    return JSONResponse(status_code=status_code, content=env.model_dump(by_alias=True))


def fail(e: ApiError) -> JSONResponse:
    """Wrap an ApiError in the unified ErrorEnvelope and return it."""
    err = ErrorObject(code=e.code, message=e.message, details=e.details)
    env = ApiEnvelope(request_id=new_request_id(), success=False, data=None, error=err)
    return JSONResponse(status_code=e.status_code, content=env.model_dump(by_alias=True))
