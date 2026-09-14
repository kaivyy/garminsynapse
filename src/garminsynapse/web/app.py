import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routes import router

logger = logging.getLogger(__name__)


async def _proactive_token_refresher():
    """Background task to proactively refresh Garmin tokens before expiry (0ms user latency)."""
    from garminsynapse.auth.manager import DualAuthManager
    while True:
        try:
            await asyncio.sleep(1800)  # Check every 30 minutes
            auth_mgr = DualAuthManager()
            auth_mgr.get_active_tokens(auto_refresh=True)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Proactive token refresh warning: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    refresh_task = asyncio.create_task(_proactive_token_refresher())
    yield
    refresh_task.cancel()


app = FastAPI(title="Garmin Synapse", lifespan=lifespan)

app.include_router(router, prefix="/api/v1")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6060)
