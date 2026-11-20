from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from fastapi_swagger_ui_theme import setup_swagger_ui_theme

from src.core.config import settings
from src.core.logging import configure_logging
from src.core.project import PROJECT_NAME, PROJECT_VERSION
from src.reference.api import router as reference_router

configure_logging(settings.log_level, settings.log_json)


def generate_operation_id(route: APIRoute) -> str:
    """Build a route's OpenAPI operation ID from its first tag and function name.

    Orval names the generated functions and hooks from these IDs, for example
    ``reference-list_states`` becomes ``useReferenceListStates``. Every route in the schema
    needs a tag. Routes left out of the schema, such as the themed ``/docs`` page, have no
    tag and use their function name, which never appears in the schema.

    Args:
        route: The route FastAPI is building an operation ID for.

    Returns:
        The operation ID, as ``<tag>-<function name>``.

    Raises:
        ValueError: if a route in the schema has no tag.
    """
    if not route.include_in_schema:
        return route.name
    if not route.tags:
        methods = ", ".join(sorted(route.methods or ()))
        message = f"Route {methods} {route.path} has no tag. Every route in the schema needs one."
        raise ValueError(message)
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title="Project Atlas",
    docs_url=None,
    generate_unique_id_function=generate_operation_id,
)
setup_swagger_ui_theme(app, docs_path="/docs")

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(reference_router)


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {
        "status": "OK",
        "name": PROJECT_NAME,
        "version": PROJECT_VERSION,
    }


app.include_router(api_v1)
