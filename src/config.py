from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    database_url: str = "postgresql+asyncpg://localhost:5432/arecca"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    storage_path: str = "data/uploads"
    app_env: str = "development"
    api_key: str = "dev-local-key"
    host: str = "0.0.0.0"
    port: int = 8000
    langsmith_api_key: str = ""
    langsmith_tracing: bool = False
    memory_encryption_key: str = ""


settings = Settings()

_config_path = Path(__file__).parent.parent / "configs" / "config.yaml"
if _config_path.exists():
    with open(_config_path) as _f:
        cfg: dict[str, Any] = yaml.safe_load(_f)
else:
    cfg = {}
