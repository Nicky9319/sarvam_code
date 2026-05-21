from typing import Optional

from pydantic import BaseModel, Field, computed_field, field_validator


class TicketParseRequest(BaseModel):
    tickets: list[str] = Field(..., max_length=500)

    @field_validator("tickets")
    @classmethod
    def tickets_max_length(cls, v: list[str]) -> list[str]:
        if len(v) > 500:
            raise ValueError("tickets list cannot exceed 500 items")
        return v

class ProcessingEstimate(BaseModel):
    estimated_batch_count: int = Field(description="Number of adaptive batches formed for this request")
    estimated_duration_seconds: float = Field(
        description="Estimated wall-clock seconds from Tier 1 baseline (~11 tickets/s) + summarization overhead"
    )


class TicketParseSuccessItem(BaseModel):
    ticket_id: str = Field(description="Stable ticket identifier assigned at ingest (1..N per request)")
    description: str = Field(description="Original ticket text from the parse request")
    classification: str = Field(description="Assigned category from classification")


class TicketParseBatchResponse(BaseModel):
    success: list[TicketParseSuccessItem]
    failures: list[str] = Field(
        description="Original ticket descriptions that failed classification"
    )
    summary: Optional[str] = Field(
        default=None,
        description="Consolidated summary of all batch summaries"
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Time in seconds taken to process the response"
    )
    processing_estimate: Optional[ProcessingEstimate] = Field(
        default=None,
        description="Pre-flight estimate computed before async worker processing begins",
    )

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
