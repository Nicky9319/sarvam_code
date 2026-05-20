from typing import Optional

import asyncio

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


class TicketParseRequest(BaseModel):
    tickets: list[str]
    estimate_only: bool = False


class TicketParseResponse(BaseModel):
    ticket_id: str
    intent: str
    priority: str
    category: str
    summary: str
    success: bool = True
    error: Optional[str] = None


class TicketParseBatchResponse(BaseModel):
    results: list[TicketParseResponse]
    total: int
    success_count: int
    failure_count: int


class ProcessTicketsRequest(BaseModel):
    tickets: list
    estimate_only: bool = False


class ProcessTicketsResponse(BaseModel):
    success_count: int
    failure_count: int
    results: list
    estimate: dict = None


class APIRoutesHandler:
    def __init__(self, application, logger, host: str = "0.0.0.0", port: int = 8000):
        self.application = application
        self.logger = logger
        self.host = host
        self.port = port
        self._app = None
        self._server = None

    def _build_app(self):

        app = FastAPI(title="TicketPipeline", version="1.0.0")
        app.add_middleware(SlowAPIMiddleware)

        # Rate limiter — keyed by client IP, 1000 req/min initially
        limiter = Limiter(key_func=get_remote_address, default_limits=["1000/minute"])
        app.state.limiter = limiter

        @app.get("/api/v1/tickets/health")
        async def health():
            return {"status": "ok"}

        return app

    async def initialize(self) -> None:
        self._app = self._build_app()
        config = uvicorn.Config(self._app, host=self.host, port=self.port, log_level="info")
        self._server = uvicorn.Server(config)
        asyncio.create_task(self._server.serve())

    async def cleanup(self) -> None:
        if self._server:
            self._server.should_exit = True

    @property
    def app(self):
        return self._app