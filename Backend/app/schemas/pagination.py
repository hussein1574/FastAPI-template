from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Sequence
import math

T = TypeVar("T")

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

class PaginatedResponse(BaseModel, Generic[T]):
    items: Sequence[T]
    total: int
    page: int
    size: int
    pages: int

    @staticmethod
    def create(items: Sequence, total: int, params: PaginationParams) -> "PaginatedResponse":
        return PaginatedResponse(
            items=items,
            total=total,
            page=params.page,
            size=params.size,
            pages=math.ceil(total / params.size) if total > 0 else 0,
        )