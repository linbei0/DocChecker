from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
    rq_queue_name: str = "docchecker"
    rq_job_timeout_seconds: int = Field(default=900, ge=1)
    rq_result_ttl_seconds: int = Field(default=86400, ge=0)
    rq_failure_ttl_seconds: int = Field(default=604800, ge=0)
    rq_retry_max: int = Field(default=3, ge=0)
    rq_retry_intervals_seconds: list[int] = Field(default_factory=lambda: [10, 60, 300])

    @field_validator("rq_queue_name")
    @classmethod
    def validate_rq_queue_name(cls, value: str) -> str:
        queue_name = value.strip()
        if not queue_name:
            raise ValueError("DOC_CHECKER_RQ_QUEUE_NAME 不能为空。")
        return queue_name

    @field_validator("rq_retry_intervals_seconds")
    @classmethod
    def validate_rq_retry_intervals(cls, value: list[int]) -> list[int]:
        if any(interval < 0 for interval in value):
            raise ValueError("DOC_CHECKER_RQ_RETRY_INTERVALS_SECONDS 不能包含负数。")
        return value

    @model_validator(mode="after")
    def validate_rq_retry_strategy(self) -> "Settings":
        if self.rq_retry_max > 0 and not self.rq_retry_intervals_seconds:
            raise ValueError("启用 RQ 重试时必须配置至少一个重试间隔。")
        return self


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
