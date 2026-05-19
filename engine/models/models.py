from typing import List

from pydantic import BaseModel, ConfigDict, Field


class TicketModel(BaseModel):
    model_config = ConfigDict(frozen=False)
    ticket_id: str
    subject: str
    description: str
    priority: str = "medium"


class ClassificationResult(BaseModel):
    model_config = ConfigDict(frozen=False)
    ticket_id: str
    category: str
    summary: str
    success: bool = True
    error: str = None


class BatchConfigModel(BaseModel):
    model_config = ConfigDict(frozen=False)
    max_context_window: int = Field(default=128000)
    avg_tokens_per_ticket: int = Field(default=2000)
    max_batch_size: int = Field(default=50)


class ProcessingStatsModel(BaseModel):
    model_config = ConfigDict(frozen=False)
    total_received: int = 0
    total_classified: int = 0
    total_failed: int = 0
    batches_processed: int = 0


class DomainState(BaseModel):
    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)
    config: BatchConfigModel = Field(default_factory=BatchConfigModel)
    stats: ProcessingStatsModel = Field(default_factory=ProcessingStatsModel)
    pending_tickets: List[TicketModel] = Field(default_factory=list)
    results: List[ClassificationResult] = Field(default_factory=list)