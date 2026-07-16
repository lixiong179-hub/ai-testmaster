import json
import logging

from app.db.database import Base
from app.db.smart_sync import smart_sync_database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("=" * 70)
logger.info("智能数据库结构同步工具")
logger.info("=" * 70)

report = smart_sync_database(Base, auto_fix=True)

logger.info("同步报告:")
logger.info(json.dumps(report, indent=2, ensure_ascii=False, default=str))

logger.info("=" * 70)
logger.info(report['summary'])
logger.info("=" * 70)
