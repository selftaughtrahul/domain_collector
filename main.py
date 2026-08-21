from fastapi import FastAPI

from database.connection import Base, engine
import models
from utils.config import settings
from utils.logger import logger

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

from api.companies import router as companies_router
app.include_router(companies_router)

from api.domains import router as domains_router
app.include_router(domains_router)

from api.analyze import router as analyze_router
app.include_router(analyze_router)


@app.get("/")
def root():
    return {
        "message": "Domain Intelligence API is running",
        "version": settings.APP_VERSION,
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

logger.info("Domain Intelligence API started")
