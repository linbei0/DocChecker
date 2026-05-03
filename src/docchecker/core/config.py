from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用运行配置。"""

    model_config = SettingsConfigDict(env_prefix="DOC_CHECKER_", env_file=".env")

    app_name: str = "DocChecker"
    checker_version: str = "0.1.0"
    storage_dir: Path = Field(default=Path("storage"))
    database_path: Path = Field(default=Path("storage/docchecker.sqlite3"))
    max_document_size_bytes: int = 30 * 1024 * 1024
    max_requirement_size_bytes: int = 20 * 1024 * 1024
    libreoffice_command: str = "soffice"
    libreoffice_conversion_timeout_seconds: int = 60
    rule_extractor_mode: Literal["local", "hybrid"] = "local"
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    task_execution_mode: Literal["inline", "rq"] = "inline"
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
