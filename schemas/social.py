from pydantic import BaseModel, ConfigDict

class SocialProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    domain_id: str
    platform: str
    url: str
