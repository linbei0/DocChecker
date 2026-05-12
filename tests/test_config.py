import pytest
from pydantic import ValidationError

from docchecker.core.config import Settings


def test_settings_accepts_rq_mode_with_queue_defaults() -> None:
    settings = Settings(task_execution_mode="rq")

    assert settings.task_execution_mode == "rq"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.rq_queue_name == "docchecker"
    assert settings.rq_retry_max == 3
    assert settings.rq_retry_intervals_seconds == [10, 60, 300]


def test_settings_rejects_empty_rq_retry_intervals_when_retries_enabled() -> None:
    with pytest.raises(ValidationError, match="至少一个重试间隔"):
        Settings(rq_retry_max=1, rq_retry_intervals_seconds=[])
