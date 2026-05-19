from engine.classes.StateStore.state_store import StateStoreSidecar
from engine.operators.api_routes_handler import APIRoutesHandler, HTTPAPIClient
from engine.operators.DB.db import DBDatabase


class TicketPipelineOperators:
    def __init__(
        self,
        logger,
        state_store_sidecar: StateStoreSidecar = None,
        sarvam_base_url: str = "https://api.sarvam.ai",
        sarvam_api_key: str = "",
    ) -> None:
        self.logger = logger
        self.state_store_sidecar = state_store_sidecar
        self.sarvam_base_url = sarvam_base_url
        self.sarvam_api_key = sarvam_api_key

    async def initialize(self) -> None:
        self._http_api_client = HTTPAPIClient(
            base_url=self.sarvam_base_url,
            api_key=self.sarvam_api_key,
            logger=self.logger,
        )

        self._db = DBDatabase(
            host="localhost",
            port=3306,
            user="root",
            password="",
            database="ticket_pipeline",
            logger=self.logger,
        )

        self._api_routes_handler = APIRoutesHandler(
            application=None,
            logger=self.logger,
            host="0.0.0.0",
            port=8000,
        )

    async def cleanup(self) -> None:
        await self._api_routes_handler.cleanup()
        await self._db.cleanup()

    @property
    def http_api_client(self):
        return self._http_api_client

    @property
    def db(self):
        return self._db

    @property
    def api_routes_handler(self):
        return self._api_routes_handler