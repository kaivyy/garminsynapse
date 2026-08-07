from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routes import router
import os

app = FastAPI(title="Garmin Synapse")

app.include_router(router, prefix="/api/v1")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6060)
