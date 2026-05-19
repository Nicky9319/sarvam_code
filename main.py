import asyncio
import os

from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv(dotenv_path=".env.local", override=True)

from engine.orchestrator import TicketPipeline


async def main():
    pipeline = TicketPipeline(
        sarvam_api_key=os.getenv("SARVAM_API_KEY", ""),
        sarvam_base_url=os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
    await pipeline.initialize()

    # Keep the server running
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await pipeline.cleanup()


if __name__ == "__main__":
    asyncio.run(main())