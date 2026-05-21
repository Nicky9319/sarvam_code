import os

from engine.classes.StateStore.state_store import StateStoreSidecar
from engine.operators.api_routes_handler import APIRoutesHandler
from engine.operators.classification_channel import ClassificationChannel
from engine.operators.db.db import DBDatabase
from engine.operators.future_manager import FutureManager
from engine.operators.http_client import HTTPAPIClient
from engine.operators.summarization_channel import SummarizationChannel


class TicketPipelineOperators:
    def __init__(
        self,
        logger,
        event_bus,
        state_store_sidecar: StateStoreSidecar = None,
        sarvam_base_url: str = "https://api.sarvam.ai/v1",
        sarvam_api_key: str = "",
    ) -> None:
        self.logger = logger
        self._event_bus = event_bus
        self.state_store_sidecar = state_store_sidecar
        self.sarvam_base_url = sarvam_base_url
        self.sarvam_api_key = sarvam_api_key

    async def initialize(self) -> None:
        self._http_api_client = HTTPAPIClient(
            sarvam_base_url=self.sarvam_base_url,
            sarvam_api_key=self.sarvam_api_key,
            logger=self.logger,
        )
        await self._http_api_client.initialize_client()

        self._db = DBDatabase(
            host=os.getenv("MONGODB_HOST", "localhost"),
            port=int(os.getenv("MONGODB_PORT", "27017")),
            logger=self.logger,
            event_bus=self._event_bus,
        )
        await self._db.initialize()

        self._classification_channel = ClassificationChannel(
            logger=self.logger,
            db_ref=self._db,
            http_api_client=self._http_api_client,
        )
        await self._classification_channel.initialize()

        self._future_manager = FutureManager(
            event_bus=self._event_bus,
            logger=self.logger,
        )
        await self._future_manager.initialize()

        self._summarization_channel = SummarizationChannel(
            logger=self.logger,
            db_ref=self._db,
            http_api_client=self._http_api_client,
            event_bus=self._event_bus,
            worker_count=5,
        )
        await self._summarization_channel.initialize()

        self._api_routes_handler = APIRoutesHandler(
            application=None,
            logger=self.logger,
            host="0.0.0.0",
            port=8000,
        )

    async def cleanup(self) -> None:
        await self._api_routes_handler.cleanup()
        await self._classification_channel.cleanup()
        await self._summarization_channel.cleanup()
        await self._future_manager.cleanup()
        await self._http_api_client.cleanup()
        await self._db.cleanup()

    @property
    def http_api_client(self):
        return self._http_api_client

    @property
    def db(self):
        return self._db

    @property
    def classification_channel(self):
        return self._classification_channel

    @property
    def api_routes_handler(self):
        return self._api_routes_handler

    @property
    def event_bus(self):
        return self._event_bus

    @property
    def future_manager(self):
        return self._future_manager

    @property
    def summarization_channel(self):
        return self._summarization_channel