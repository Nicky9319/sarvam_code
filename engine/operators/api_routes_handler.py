from typing import Optional, TYPE_CHECKING
import asyncio
import os
import uvicorn
from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import CollectorRegistry, multiprocess, REGISTRY
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

from classes.Logger.logger import LogSidecar

if TYPE_CHECKING:
    from engine.application import TicketPipelineApplication


from engine.models.api_request_models import (
    TicketParseRequest,
    TicketParseBatchResponse
)


# ---------------------------------------------------------------------------
# API handler
# ---------------------------------------------------------------------------

class APIRoutesHandler:
    def __init__(self, application: "TicketPipelineApplication", logger: LogSidecar, host: str = "0.0.0.0", port: int = 8000):
        self.application: "TicketPipelineApplication" = application
        self.logger: LogSidecar = logger
        self.host: str = host
        self.port: int = port

        self._app: Optional[FastAPI] = None
        self._server: Optional[uvicorn.Server] = None
        self._task: Optional[asyncio.Task] = None

        self._limiter: Limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["1000/minute"],
        )

    @staticmethod
    def _make_registry() -> CollectorRegistry:
        """
        Create a Prometheus registry.

        If PROMETHEUS_MULTIPROC_DIR is set we use the multiprocess
        collector so that all uvicorn workers share metrics correctly.
        Otherwise fall back to the default global registry.

        Processing Steps:
        Step 1: Check for PROMETHEUS_MULTIPROC_DIR environment variable
        Step 2: Return multiprocess registry if set, otherwise return global registry
        """
        multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        if multiproc_dir:
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            return registry
        return REGISTRY

    def _rate_limit_handler(self, request: Request, exc: RateLimitExceeded):
        """
        Handle rate limit exceeded errors.

        Processing Steps:
        Step 1: Return 429 JSON response with error detail
        """
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded: {exc.detail}"},
        )

    async def _register_routes(self, app: FastAPI) -> None:
        """
        Register all API routes on the FastAPI app.

        Processing Steps:
        Step 1: Register health endpoint
        Step 2: Register parse tickets endpoint
        """
        await self.logger.debug("Starting step 1: Registering health endpoint")

        @app.get("/api/v1/tickets/health")
        @self._limiter.limit("10/minute")
        async def health(request: Request):
            return {"status": "ok"}

        await self.logger.debug("Step 1 completed")

        await self.logger.debug("Starting step 2: Registering parse tickets endpoint")

        @app.post("/api/v1/tickets/parse", response_model=TicketParseBatchResponse)
        @self._limiter.limit("5/minute")
        async def parse_tickets(request: Request, body: TicketParseRequest):
            return TicketParseBatchResponse(
                results=[],
                total=len(body.tickets),
                success_count=0,
                failure_count=0,
            )

        await self.logger.debug("Step 2 completed")

    async def initialize(self) -> None:
        """
        Build the FastAPI app, configure uvicorn, but do not start serving.

        This method builds the FastAPI app, configures uvicorn, and registers
        all routes. It sets up rate limiting, Prometheus instrumentation.

        Processing Steps:
        Step 1: Build FastAPI app with middleware and configuration
        Step 2: Configure uvicorn server
        """
        try:
            await self.logger.info(
                "Function started",
                host=self.host,
                port=self.port,
            )

            # Step 1: Build FastAPI app
            await self.logger.debug("Starting step 1: Building FastAPI app")

            app: FastAPI = FastAPI(title="TicketPipeline", version="1.0.0")

            app.state.limiter = self._limiter
            app.add_middleware(SlowAPIMiddleware)
            app.add_exception_handler(RateLimitExceeded, self._rate_limit_handler)

            registry = self._make_registry()
            Instrumentator(
                registry=registry,
                excluded_handlers=["/metrics"],
            ).instrument(app).expose(app, include_in_schema=False)

            await self._register_routes(app)

            await self.logger.debug("Step 1 completed")

            # Step 2: Configure uvicorn server
            await self.logger.debug("Starting step 2: Configuring uvicorn server")

            self._app = app
            config = uvicorn.Config(
                self._app,
                host=self.host,
                port=self.port,
                log_level="info",
            )
            self._server = uvicorn.Server(config)

            await self.logger.debug("Step 2 completed")

            await self.logger.info(
                "Function ended successfully",
                host=self.host,
                port=self.port,
            )

        except Exception as e:
            await self.logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def cleanup(self) -> None:
        """
        Stop the uvicorn server gracefully.

        Processing Steps:
        Step 1: Signal server to exit
        Step 2: Await task completion
        """
        try:
            await self.logger.info("Function started")

            await self.logger.debug("Starting step 1: Signaling server exit")
            if self._server:
                self._server.should_exit = True
            await self.logger.debug("Step 1 completed")

            await self.logger.debug("Starting step 2: Awaiting task completion")
            if self._task:
                await self._task
            await self.logger.debug("Step 2 completed")

            await self.logger.info("Function ended successfully")

        except Exception as e:
            await self.logger.error(
                "Function ended with exception",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    @property
    def app(self) -> Optional[FastAPI]:
        return self._app
    
