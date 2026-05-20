from typing import Optional

from pydantic import BaseModel, Field, field_validator, computed_field


class TicketParseRequest(BaseModel):
    tickets: list[str] = Field(..., max_length=500)

    @field_validator("tickets")
    @classmethod
    def tickets_max_length(cls, v: list[str]) -> list[str]:
        if len(v) > 500:
            raise ValueError("tickets list cannot exceed 500 items")
        return v

class TicketParseBatchResponse(BaseModel):
    success: list[dict[str , str]]
    failures: list[str]

    @computed_field 
    def total(self) -> int:
        return len(self.success) + len(self.failures)
    
    @computed_field
    def success_count(self) -> int:
        return len(self.success)
    
    @computed_field
    def failure_count(self) -> int:
        return len(self.failures)



class HealthCheckResponse(BaseModel):
    status: str = "ok" 
