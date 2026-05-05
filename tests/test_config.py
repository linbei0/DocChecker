import pytest
from pydantic import ValidationError

from docchecker.core.config import Settings


def test_settings_rejects_unimplemented_rq_mode() -> None:
    with pytest.raises(ValidationError, match="rq 已预留但尚未实现"):
        Settings(task_execution_mode="rq")
