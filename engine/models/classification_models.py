from typing import List, Optional

from pydantic import BaseModel, Field


class TickerInformation(BaseModel):
    ticket_id: str
    description: str


class ClassificationRequestMessageInputModel(BaseModel):
    tickets: List[TickerInformation]


class TicketClassificationResult(BaseModel):
    ticket_id: str
    category: str


class ClassificationResponseModel(BaseModel):
    ticket_classifications: List[TicketClassificationResult] = Field(default_factory=list)
    summary: Optional[str] = None
