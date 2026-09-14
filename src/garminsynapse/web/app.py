import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
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


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Ensure static files (.css, .js, .html) are never stale in browser."""
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith(("/css", "/js", "/static")) or request.url.path == "/" or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app = FastAPI(title="Garmin Synapse", lifespan=lifespan)
app.add_middleware(NoCacheStaticMiddleware)

app.include_router(router, prefix="/api/v1")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6060)
