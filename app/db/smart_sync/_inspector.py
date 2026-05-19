import logging
from typing import List, Dict, Tuple, Optional

from sqlalchemy import inspect

logger = logging.getLogger(__name__)


class _InspectorMixin:
    def get_model_columns(self, table_name: str, Base) -> List[Dict]:
        if table_name not in Base.metadata.tables:
            return []

        table = Base.metadata.tables[table_name]
        columns = []

        for column in table.columns:
            col_info = {
                'name': column.name,
                'type': str(column.type),
                'nullable': column.nullable,
                'default': self._resolve_sql_default(column),
                'primary_key': column.primary_key,
                'comment': column.comment or ''
            }
            columns.append(col_info)

        return columns

    def _resolve_sql_default(self, column) -> Optional[str]:
        server_default = column.server_default
        if server_default is not None:
            arg = getattr(server_default, 'arg', None)
            if arg is not None:
                if hasattr(arg, 'text'):
                    return arg.text
                return str(arg)

        col_default = column.default
        if col_default is None:
            return None

        arg = getattr(col_default, 'arg', None)
        if arg is None:
            return None
        if isinstance(arg, bool):
            return '1' if arg else '0'
        if isinstance(arg, (int, float)):
            return str(arg)
        if isinstance(arg, str):
            return f"'{arg}'"
        return str(arg)

    def get_db_columns(self, table_name: str) -> List[Dict]:
        try:
            columns = self.inspector.get_columns(table_name)
            return [{
                'name': col['name'],
                'type': str(col['type']),
                'nullable': col.get('nullable', True),
                'default': str(col.get('default')) if col.get('default') else None,
                'primary_key': col.get('primary_key', False),
                'comment': col.get('comment', '')
            } for col in columns]
        except Exception as e:
            logger.warning(f"无法获取表 {table_name} 的列信息: {e}")
            return []

    def find_missing_columns(self, table_name: str, Base) -> Tuple[List[Dict], List[str]]:
        model_cols = self.get_model_columns(table_name, Base)
        db_cols = self.get_db_columns(table_name)

        db_col_names = {col['name'] for col in db_cols}
        missing_cols = [col for col in model_cols if col['name'] not in db_col_names]

        return missing_cols, list(db_col_names)
