from classes.BaseReducers.base_reducers import BaseReducers
from classes.Logger.logger import LogAgent
from engine.classes.StateStore.state_store import StateStoreSidecar


class TicketPipelineReducers(BaseReducers):
    def __init__(
        self,
        logger: LogAgent,
        state_store_sidecar: StateStoreSidecar = None,
    ) -> None:
        super().__init__(logger=logger, state_store_sidecar=state_store_sidecar)

    async def initialize(self) -> None:
        from engine.models.models import DomainState
        await super().initialize(DomainState())