from pydantic import BaseModel, ConfigDict


class RequirementDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    filename: str
    path: str
    size_bytes: int
    extracted_text: str
    created_at: str
