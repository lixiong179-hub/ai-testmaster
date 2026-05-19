"""数据库结构检查模块 - ORM模型与数据库表结构差异检测"""
import logging
import re
from typing import List, Dict, Tuple, Any, Optional

from sqlalchemy import inspect

logger = logging.getLogger(__name__)


class SchemaInspectorMixin:
    """数据库结构检查混入类 - 列名验证、模型/数据库列信息获取、差异检测。"""

    COLUMN_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    COLUMN_TYPE_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_() ,.]*$')
    SQL_INJECTION_PATTERN = re.compile(r'[;\'"\\-]', re.IGNORECASE)

    def _validate_column_name(self, name: str) -> bool:
        """验证列名是否符合安全命名规范，防止SQL注入。"""
        if not name or not isinstance(name, str):
            return False
        return bool(self.COLUMN_NAME_PATTERN.match(name))

    def _init_inspector(self, engine: Any = None) -> None:
        """初始化同步工具的引擎和检查器。

        Args:
            engine: SQLAlchemy引擎实例，为None时从 app.db.database 导入默认引擎。
        """
        if engine is not None:
            self.engine = engine
        else:
            from app.db.database import engine as default_engine
            self.engine = default_engine
        self.inspector = inspect(self.engine)

    def get_model_columns(self, table_name: str, Base) -> List[Dict]:
        """获取ORM模型定义的列信息。

        Args:
            table_name: 表名
            Base: SQLAlchemy 声明式基类

        Returns:
            列信息字典列表，表名不存在时返回空列表
        """
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
        """解析列的 SQL DEFAULT 值，优先 server_default，其次解析 column.default。"""
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
        """获取数据库实际的列信息，表不存在时返回空列表。"""
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
        """检测ORM模型中有但数据库中缺失的列。

        Returns:
            (缺失列信息列表, 数据库中已存在的列名列表)
        """
        model_cols = self.get_model_columns(table_name, Base)
        db_cols = self.get_db_columns(table_name)

        db_col_names = {col['name'] for col in db_cols}
        missing_cols = [col for col in model_cols if col['name'] not in db_col_names]

        return missing_cols, list(db_col_names)
