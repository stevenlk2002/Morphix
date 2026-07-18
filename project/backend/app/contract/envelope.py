import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class DTO(BaseModel):
    """Base for all request/response DTOs.

    Contract uses camelCase wire names; we keep snake_case Python fields and
    generate camelCase aliases automatically.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ApiEnvelope(DTO):
    request_id: str
    success: bool
    data: Any = None
    error: Any = None


class ErrorObject(DTO):
    code: str
    message: str
    details: list[dict] | None = None


class ApiError(Exception):
    """Raised inside routers; converted to an ErrorEnvelope by the handler."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def new_request_id() -> str:
    return uuid.uuid4().hex
