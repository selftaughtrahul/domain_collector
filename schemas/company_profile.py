from pydantic import BaseModel, ConfigDict
from typing import Optional

class CompanyProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    domain_id: str
    name: Optional[str] = None
    legal_name: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    contact_page: Optional[str] = None
    about_page: Optional[str] = None
    careers_page: Optional[str] = None
    pricing_page: Optional[str] = None
    services: Optional[str] = None
    business_hours: Optional[str] = None
