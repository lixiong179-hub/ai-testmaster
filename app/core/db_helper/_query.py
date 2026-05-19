from sqlalchemy.orm import Session, Query
from typing import TypeVar, Type, Any

T = TypeVar('T')


class QueryHelper:
    @staticmethod
    def build_filter_conditions(model: Type[T], **filters) -> list:
        conditions = []
        for field, value in filters.items():
            if value is not None and hasattr(model, field):
                conditions.append(getattr(model, field) == value)
        return conditions

    @staticmethod
    def build_pagination(query, page: int = 1, page_size: int = 10):
        offset = (page - 1) * page_size
        return offset, page_size


def paginate_query(db: Session, query: Query, page: int = 1, page_size: int = 10) -> dict[str, Any]:
    total = query.count()
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()
    return items, total
