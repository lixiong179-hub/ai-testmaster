import time
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, InterfaceError
from typing import Callable, Any
from loguru import logger


class TransactionHelper:
    @staticmethod
    def with_transaction(
        db: Session, operation: Callable[..., Any], *args, **kwargs
    ) -> Any:
        last_exception = None
        for attempt in range(3):
            try:
                result = operation(*args, **kwargs)
                db.commit()
                return result
            except Exception as e:
                last_exception = e
                logger.error(
                    f"事务操作失败, 回滚(第{attempt + 1}次): "
                    f"[{type(e).__name__}] {e}, "
                    f"会话: active={db.is_active if hasattr(db, 'is_active') else 'N/A'}"
                )
                try:
                    db.rollback()
                except Exception as rollback_err:
                    logger.error(f"回滚失败: {rollback_err}")
                if not isinstance(e, (OperationalError, InterfaceError)):
                    raise
                if attempt < 2:
                    time.sleep(1 * (attempt + 1))
                    continue
                raise
        raise last_exception

    @staticmethod
    def safe_execute(
        db: Session, operation: Callable[..., Any], *args, **kwargs
    ) -> tuple[bool, Any]:
        try:
            result = operation(*args, **kwargs)
            db.commit()
            return True, result
        except Exception as e:
            logger.error(
                f"操作失败: [{type(e).__name__}] {e}, "
                f"会话: active={db.is_active if hasattr(db, 'is_active') else 'N/A'}"
            )
            try:
                db.rollback()
            except Exception as rollback_err:
                logger.error(f"回滚失败: {rollback_err}")
            return False, str(e)
