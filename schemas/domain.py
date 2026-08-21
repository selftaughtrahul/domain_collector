from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class DomainCreate(BaseModel):
    domain: str
    domain_type: str = "primary"
    is_primary: bool = False

class DomainRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_id: str
    domain: str
    domain_type: str
    is_primary: bool
    is_active: bool
    scan_status: str
    last_scanned_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
