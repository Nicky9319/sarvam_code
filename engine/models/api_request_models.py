from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TicketParseRequest(BaseModel):
    tickets: list[str] = Field(..., max_length=500)
    estimate_only: bool = False

    @field_validator("tickets")
    @classmethod
    def tickets_max_length(cls, v: list[str]) -> list[str]:
        if len(v) > 500:
            raise ValueError("tickets list cannot exceed 500 items")
        return v


class TicketParseResponse(BaseModel):
    ticket_id: str
    intent: str
    priority: str
    category: str
    summary: str
    success: bool = True
    error: Optional[str] = None


class TicketParseBatchResponse(BaseModel):
    results: list[TicketParseResponse]
    total: int
    success_count: int
    failure_count: int

