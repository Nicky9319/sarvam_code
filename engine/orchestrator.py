from classes.Logger.logger import LogFormat, Logger
from engine.application import TicketPipelineApplication
from engine.classes.StateStore.state_store import StateStoreSidecar
from engine.event_bus import EventBus
from engine.operators.operators import TicketPipelineOperators
from engine.reducers import TicketPipelineReducers


class TicketPipeline:
    def __init__(
        self,
        sarvam_api_key: str = "",
        sarvam_base_url: str = "https://api.sarvam.ai/v1",
        log_level: str = "INFO",
        state_store_sidecar: StateStoreSidecar = None,
    ) -> None:
        self.sarvam_api_key = sarvam_api_key
        self.sarvam_base_url = sarvam_base_url
        self.state_store_sidecar = state_store_sidecar
        self.logger = Logger(log_format=LogFormat.NORMAL)
        self._log_level = log_level

    async def initialize(self) -> None:
        await self.logger.set_level(self._log_level)
        self._logger_agent = await self.logger.get_agent("ticket_pipeline")

        self.event_bus = EventBus(
            logger=await self._logger_agent.get_sidecar("event_bus"),
        )

        self.reducers = TicketPipelineReducers(
            logger=await self._logger_agent.get_sidecar("reducers"),
            state_store_sidecar=self.state_store_sidecar,
            event_bus=self.event_bus,
        )
        await self.reducers.initialize()

        self.operators = TicketPipelineOperators(
            logger=await self._logger_agent.get_sidecar("operators"),
            state_store_sidecar=self.state_store_sidecar,
            sarvam_base_url=self.sarvam_base_url,
            sarvam_api_key=self.sarvam_api_key,
            event_bus=self.event_bus,
        )
        await self.operators.initialize()

        self.application = TicketPipelineApplication(
            reducers=self.reducers,
            logger=await self._logger_agent.get_sidecar("application"),
            operators=self.operators,
            event_bus=self.event_bus,
        )
        await self.application.initialize()

        # Wire application into API routes handler
        self.operators._api_routes_handler.application = self.application

        # Start FastAPI server
        await self.operators._api_routes_handler.initialize()

    async def cleanup(self) -> None:
        await self.operators.cleanup()
        await self.event_bus.cleanup()