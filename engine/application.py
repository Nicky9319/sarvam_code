from typing import Optional

from engine.operators.operators import TicketPipelineOperators


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