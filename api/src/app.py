from fastapi import APIRouter, FastAPI

app = FastAPI(title="Project Atlas")

api_v1 = APIRouter(prefix="/api/v1")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_v1)
