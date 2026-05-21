from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RequestRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    request_id: str
    state: Literal["classification", "summarization", "completed"]
    response_summary: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime


class BatchRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    batch_id: str
    batch_number: int
    request_id: str
    batch_state: Literal["queued", "processing", "processed"]
    batch_summary: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime


class TicketRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket_id: str
    request_id: str
    batch_id: str
    content: str
    state: Literal["completed", "queued", "failed"]
    batch_number: int
    response: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime


class AddRequestOutput(BaseModel):
    request_id: str


class AddBatchOutput(BaseModel):
    batch_id: str
    batch_number: int


class AddTicketOutput(BaseModel):
    ticket_id: str


class TicketUpdateItem(BaseModel):
    ticket_id: str
    state: Literal["completed", "failed"]
    response: Optional[str] = None


class UpdateBatchInput(BaseModel):
    batch_id: str
    batch_state: Literal["queued", "processing", "processed"]
    batch_summary: Optional[str] = None
    ticket_updates: Optional[List[TicketUpdateItem]] = None
    mark_all_tickets_failed: bool = Field(
        default=False,
        description="When true, mark every ticket in the batch as failed",
    )


class UpdateBatchOutput(BaseModel):
    batch_id: str
    request_id: str
    all_batches_completed: bool
    event_emitted: bool = False


class GetAllBatchesCompletedOutput(BaseModel):
    completed: bool


class BatchSummaryItem(BaseModel):
    batch_number: int
    summary: str


class TicketResponseOutput(BaseModel):
    ticket_id: str
    content: str
    state: str
    response: Optional[str] = None
    batch_number: int


class GetTickerResponsesOutput(BaseModel):
    responses: List[TicketResponseOutput]


class GetBatchInfoAndTicketsOutput(BaseModel):
    batch: Optional[BatchRecord] = None
    tickets: List[TicketRecord]
