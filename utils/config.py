from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Domain Intelligence API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./domain_intelligence.db"
    LOG_LEVEL: str = "INFO"
    REQUEST_TIMEOUT: float = 12.0
    USER_AGENT: str = "DomainIntelligenceBot/1.0 (+local business research)"
    MAX_PAGE_SIZE: int = 2_000_000
    MAX_RESPONSE_SIZE: int = 2_000_000
    MAX_PAGES_PER_SCAN: int = 3
    REQUEST_DELAY: float = 0.0
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")

settings = Settings()
