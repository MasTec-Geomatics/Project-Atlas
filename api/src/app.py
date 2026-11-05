from fastapi import APIRouter, FastAPI

from src.core.config import settings
from src.core.logging import configure_logging

configure_logging(settings.log_level)

app = FastAPI(title="Project Atlas")

api_v1 = APIRouter(prefix="/api/v1")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_v1)
