import asyncio
import os

from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv(dotenv_path=".env.local", override=True)

from engine.orchestrator import TicketPipeline


async def main():
    pipeline = TicketPipeline(
        sarvam_api_key=os.getenv("SARVAM_API_KEY", ""),
        sarvam_base_url=os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai/v1"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
    await pipeline.initialize()

    api_handler = pipeline.operators.api_routes_handler
    server = api_handler._server
    task = asyncio.ensure_future(server.serve())

    # Keep the server running
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        await pipeline.cleanup()


if __name__ == "__main__":
    asyncio.run(main())