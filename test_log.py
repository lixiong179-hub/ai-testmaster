import sys
sys.path.insert(0, '.')
from app.core.logging import setup_logging
from app.core.config import settings
from loguru import logger

print(f"settings.LOG_LEVEL: {settings.LOG_LEVEL}")

setup_logging(log_level=settings.LOG_LEVEL)

logger.debug("This is a DEBUG message")
logger.info("This is an INFO message")
logger.warning("This is a WARNING message")
logger.error("This is an ERROR message")

print("Done!")