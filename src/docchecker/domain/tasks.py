from pydantic import BaseModel, ConfigDict

from docchecker.domain.enums import TaskStatus


class CheckTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    ruleset_id: str
    status: TaskStatus
    report_id: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str
