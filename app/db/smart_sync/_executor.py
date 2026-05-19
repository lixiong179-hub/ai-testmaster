import logging
from typing import List, Dict

from sqlalchemy import text

logger = logging.getLogger(__name__)


class _ExecutorMixin:
    def generate_add_column_sql(self, table_name: str, col_info: Dict) -> str:
        col_name = col_info['name']
        if not self._validate_column_name(col_name):
            raise ValueError(f"Invalid column name: {col_name}")
        col_type = col_info['type']
        if not self.COLUMN_TYPE_PATTERN.match(col_type):
            raise ValueError(f"Invalid column type: {col_type}")
        nullable = "NULL" if col_info['nullable'] else "NOT NULL"
        default_raw = col_info['default']
        default = ""
        if default_raw and default_raw != 'None':
            if self.SQL_INJECTION_PATTERN.search(str(default_raw)):
                raise ValueError(f"Invalid default value: {default_raw}")
            default = f" DEFAULT {default_raw}"
        comment_raw = col_info.get('comment', '')
        comment = ""
        if comment_raw:
            escaped_comment = str(comment_raw).replace("'", "\\'")
            comment = f" COMMENT '{escaped_comment}'"

        sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {nullable}{default}{comment}"
        return sql

    def sync_table(self, table_name: str, Base, auto_fix: bool = True) -> Dict:
        result = {
            'table': table_name,
            'status': 'ok',
            'missing_columns': [],
            'fixed_columns': [],
            'errors': []
        }

        try:
            missing_cols, existing_cols = self.find_missing_columns(table_name, Base)

            if not missing_cols:
                result['status'] = 'synced'
                return result

            result['status'] = 'out_of_sync'
            result['missing_columns'] = [col['name'] for col in missing_cols]
            result['existing_columns'] = existing_cols

            logger.warning(f"表 {table_name} 缺少 {len(missing_cols)} 个字段: {[c['name'] for c in missing_cols]}")

            if not auto_fix:
                return result

            with self.engine.connect() as conn:
                for col in missing_cols:
                    try:
                        sql = self.generate_add_column_sql(table_name, col)
                        conn.execute(text(sql))
                        result['fixed_columns'].append(col['name'])
                        logger.info(f"✓ 已添加列: {table_name}.{col['name']}")
                    except Exception as e:
                        error_msg = f"添加列 {col['name']} 失败: {e}"
                        result['errors'].append(error_msg)
                        logger.error(f"✗ {error_msg}")

                conn.commit()

            if result['errors']:
                result['status'] = 'partial_fix'
            elif result['fixed_columns']:
                result['status'] = 'fixed'

        except Exception as e:
            result['status'] = 'error'
            result['errors'].append(str(e))
            logger.error(f"同步表 {table_name} 时出错: {e}")

        return result

    def sync_all_tables(self, Base, auto_fix: bool = True, exclude_tables: List[str] = None) -> Dict:
        report = {
            'total_tables': 0,
            'synced': 0,
            'out_of_sync': 0,
            'fixed': 0,
            'errors': 0,
            'details': [],
            'summary': ''
        }

        exclude_tables = exclude_tables or []

        model_tables = list(Base.metadata.tables.keys())
        report['total_tables'] = len(model_tables)

        for table_name in model_tables:
            if table_name in exclude_tables:
                continue

            result = self.sync_table(table_name, Base, auto_fix=auto_fix)
            report['details'].append(result)

            status = result['status']
            if status == 'synced':
                report['synced'] += 1
            elif status == 'out_of_sync':
                report['out_of_sync'] += 1
            elif status == 'fixed':
                report['fixed'] += 1
            elif status == 'partial_fix':
                report['fixed'] += 1
                report['errors'] += 1
            elif status == 'error':
                report['errors'] += 1

        fixed_count = sum(len(d.get('fixed_columns', [])) for d in report['details'])
        report['summary'] = (
            f"检查了 {report['total_tables']} 个表，"
            f"{report['synced']} 个已同步，"
            f"{report['fixed']} 个已修复，"
            f"共添加 {fixed_count} 个缺失字段"
        )

        return report
