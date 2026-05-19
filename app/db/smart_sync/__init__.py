import logging
from typing import Dict, Any

from sqlalchemy import inspect

from app.db.smart_sync._validation import _ValidationMixin
from app.db.smart_sync._inspector import _InspectorMixin
from app.db.smart_sync._executor import _ExecutorMixin

logger = logging.getLogger(__name__)


class DatabaseSyncTool(_ValidationMixin, _InspectorMixin, _ExecutorMixin):
    def __init__(self, engine: Any = None) -> None:
        if engine is not None:
            self.engine = engine
        else:
            from app.db.database import engine as default_engine
            self.engine = default_engine
        self.inspector = inspect(self.engine)


def smart_sync_database(Base, auto_fix: bool = True) -> Dict:
    tool = DatabaseSyncTool()
    report = tool.sync_all_tables(Base, auto_fix=auto_fix)

    if report['fixed'] > 0 or report['out_of_sync'] > 0:
        logger.warning(f"数据库同步完成: {report['summary']}")
        for detail in report['details']:
            if detail['status'] in ['fixed', 'partial_fix', 'out_of_sync']:
                logger.info(
                    f"表 {detail['table']}: "
                    f"修复了 {len(detail.get('fixed_columns', []))} 个字段"
                )
    else:
        logger.info("数据库检查完成: 所有表结构已同步")

    return report


__all__ = ['DatabaseSyncTool', 'smart_sync_database']
