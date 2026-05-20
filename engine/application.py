from typing import Optional

from engine.operators.operators import TicketPipelineOperators
from engine.models.api_request_models import TicketParseBatchResponse, TicketParseRequest


class TicketPipelineApplication:
    def __init__(
        self,
        reducers,
        logger,
        operators: Optional[TicketPipelineOperators] = None,
    ) -> None:
        self.reducers = reducers
        self.logger = logger
        self.operators = operators

    async def initialize(self) -> None:
        pass

    async def process_tickets_request(self, request: TicketParseRequest) -> TicketParseBatchResponse:
        # To do
        pass