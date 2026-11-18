from typing import Generic, TypeVar

from pydantic import BaseModel


DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    code: int = 0
    message: str = "ok"
    data: DataT


class ApiErrorResponse(BaseModel):
    code: int
    message: str
    data: None = None
