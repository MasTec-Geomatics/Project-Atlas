from fastapi import APIRouter, FastAPI
from fastapi_swagger_ui_theme import setup_swagger_ui_theme

from src.core.config import settings
from src.core.logging import configure_logging
from src.core.project import PROJECT_NAME, PROJECT_VERSION
from src.reference.api import router as reference_router

configure_logging(settings.log_level, settings.log_json)

app = FastAPI(title="Project Atlas", docs_url=None)
setup_swagger_ui_theme(app, docs_path="/docs")

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(reference_router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {
        "status": "OK",
        "name": PROJECT_NAME,
        "version": PROJECT_VERSION,
    }


app.include_router(api_v1)
