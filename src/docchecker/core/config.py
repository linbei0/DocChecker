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
    max_document_size_bytes: int = 30 * 1024 * 1024
    max_requirement_size_bytes: int = 20 * 1024 * 1024
    task_execution_mode: Literal["inline", "rq"] = "inline"
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
