import logging

from utils.config import settings


def setup_logger() -> logging.Logger:

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    return logging.getLogger("domain_intelligence")


logger = setup_logger()
