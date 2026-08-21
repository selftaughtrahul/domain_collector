from pydantic import BaseModel, ConfigDict

class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    domain_id: str
    kind: str
    value: str
    source_url: str | None
