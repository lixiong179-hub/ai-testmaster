from sqlalchemy.orm import Session
from typing import Optional, List, TypeVar, Type
from loguru import logger

T = TypeVar('T')


class DatabaseHelper:
    @staticmethod
    def get_by_id(db: Session, model: Type[T], id: int) -> Optional[T]:
        return db.query(model).filter(model.id == id).first()

    @staticmethod
    def get_by_ids(db: Session, model: Type[T], ids: List[int]) -> List[T]:
        if not ids:
            return []
        return db.query(model).filter(model.id.in_(ids)).all()

    @staticmethod
    def get_all(db: Session, model: Type[T], skip: int = 0, limit: int = 100) -> List[T]:
        return db.query(model).offset(skip).limit(limit).all()

    @staticmethod
    def count(db: Session, model: Type[T], **filters) -> int:
        query = db.query(model)
        if filters:
            query = query.filter_by(**filters)
        return query.count()

    @staticmethod
    def create(db: Session, model: Type[T], **kwargs) -> T:
        instance = model(**kwargs)
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance

    @staticmethod
    def update(db: Session, instance: T, **kwargs) -> T:
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        db.commit()
        db.refresh(instance)
        return instance

    @staticmethod
    def delete(db: Session, instance: T) -> bool:
        try:
            db.delete(instance)
            db.commit()
            return True
        except Exception as e:
            logger.error(
                f"删除记录失败: [{type(e).__name__}] {e}, "
                f"实例类型: {type(instance).__name__}, "
                f"会话: active={db.is_active if hasattr(db, 'is_active') else 'N/A'}"
            )
            db.rollback()
            return False

    @staticmethod
    def safe_commit(db: Session) -> bool:
        try:
            db.commit()
            return True
        except Exception as e:
            logger.error(
                f"事务提交失败: [{type(e).__name__}] {e}, "
                f"会话: active={db.is_active if hasattr(db, 'is_active') else 'N/A'}"
            )
            db.rollback()
            return False
