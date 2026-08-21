from pydantic import BaseModel, ConfigDict
from datetime import datetime

class WebsiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    domain_id: str
    final_url: str | None
    status_code: int | None
    title: str | None
    meta_description: str | None
    language: str | None
    favicon_url: str | None
    content_type: str | None
    server: str | None
    page_size: int | None
    redirect_chain: str | None
    response_headers: str | None
    headings: str | None
    page_text: str | None
    image_count: int
    script_count: int
    stylesheet_count: int
    robots_url: str | None
    sitemap_url: str | None
    updated_at: datetime
