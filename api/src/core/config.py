import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, PostgresDsn

# api/src/core/config.py -> repository root, where .env lives.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    database_url: PostgresDsn = Field(alias="DATABASE_URL")
    api_host: str = Field(alias="API_HOST")
    api_port: int = Field(alias="API_PORT")
    log_level: str = Field(alias="LOG_LEVEL")
    log_json: bool = Field(alias="LOG_JSON")


_ = load_dotenv(REPO_ROOT / ".env")
settings = Settings.model_validate(os.environ)
