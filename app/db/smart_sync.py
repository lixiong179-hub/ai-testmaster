"""
智能数据库同步工具 - 自动检测并修复ORM模型与数据库表结构差异

本模块解决的核心问题：
    SQLAlchemy 的 create_all() 只能创建不存在的表，无法处理已有表的结构变更
    （如新增字段）。当开发者在 ORM 模型中添加了新字段但忘记执行数据库迁移时，
    应用会因为访问不存在的列而报错。本工具在应用启动时自动检测并修复这类问题。

核心类/函数概览：
- DatabaseSyncTool: 数据库结构同步工具类
    - _validate_column_name(): 列名安全验证（防SQL注入）
    - get_model_columns(): 获取ORM模型定义的列信息
    - get_db_columns(): 获取数据库实际的列信息
    - find_missing_columns(): 检测模型中有但数据库中缺失的列
    - generate_add_column_sql(): 生成 ALTER TABLE ADD COLUMN SQL
    - sync_table(): 同步单个表的结构
    - sync_all_tables(): 同步所有表的结构
- smart_sync_database(): 便捷同步函数，创建工具实例并执行全表同步

使用场景：
1. 应用启动时自动运行（在 init_db() 中调用）
2. 手动修复表结构问题（命令行执行 python -m app.db.smart_sync）
3. CI/CD流水线中的数据库检查（auto_fix=False，仅检测不修复）

与 Alembic 的关系（互补而非替代）：
    Alembic:
        - 专业的数据库迁移工具，支持增删改列、索引、约束等所有变更
        - 需要手动生成和执行迁移脚本（alembic revision / alembic upgrade）
        - 适合有规划的版本化迁移管理
    smart_sync:
        - 仅处理"新增字段"这一最常见场景
        - 自动检测并修复，无需手动干预
        - 适合防止因遗漏迁移脚本导致的运行时错误
    推荐做法：日常开发使用 Alembic 管理迁移，smart_sync 作为安全兜底

安全设计：
    - 列名验证：通过正则白名单验证列名，防止SQL注入
    - auto_fix 参数：默认 True 自动修复，可设为 False 仅检测
    - 不处理列删除/修改：避免误删数据，仅做增量操作
    - 错误隔离：单列添加失败不影响其他列，记录错误继续执行

依赖关系：
- app.core.config.settings: 数据库连接配置
- app.db.database.engine: 默认数据库引擎（当未显式传入时使用）

同步报告状态流转：
    synced       -> 表结构完全一致，无需操作
    out_of_sync  -> 检测到缺失字段，但 auto_fix=False 未修复
    fixed        -> 所有缺失字段已成功添加
    partial_fix  -> 部分字段添加成功，部分失败
    error        -> 同步过程发生异常
"""

import sys
import os
import logging
import re
from typing import List, Dict, Tuple, Any

# 将当前目录加入 sys.path，确保直接执行时能正确导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, inspect

logger = logging.getLogger(__name__)


class DatabaseSyncTool:
    """
    数据库结构同步工具 - 检测并修复ORM模型与数据库表的结构差异

    职责：
        比较 SQLAlchemy ORM 模型定义的表结构与数据库中实际表结构的差异，
        自动生成并执行 ALTER TABLE 语句添加缺失的列。

    设计意图：
        作为 create_all() 的补充，解决"新增字段后忘记执行迁移"的问题。
        仅做增量操作（添加列），不做破坏性操作（删除/修改列），保证数据安全。

    关键属性：
        engine: SQLAlchemy 数据库引擎实例
        inspector: SQLAlchemy 检查器，用于获取数据库元信息（表结构、列信息等）

    使用场景：
        1. 应用启动时自动同步（init_db 中调用）
        2. 手动执行数据库检查和修复
        3. CI/CD 流水线中的数据库一致性验证

    使用示例：
        tool = DatabaseSyncTool()
        report = tool.sync_all_tables(Base, auto_fix=True)
        print(report['summary'])
    """

    # 列名合法正则：以字母或下划线开头，仅包含字母、数字、下划线
    # 此正则用于白名单验证，防止恶意列名导致的SQL注入攻击
    # 合法示例：user_name, id, create_time, is_active
    # 非法示例：name; DROP TABLE users--, 1col, col-name
    COLUMN_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    COLUMN_TYPE_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_() ,.]*$')
    SQL_INJECTION_PATTERN = re.compile(r'[;\'"\\-]', re.IGNORECASE)

    def _validate_column_name(self, name: str) -> bool:
        """
        验证列名是否符合安全命名规范

        安全目的：
            在生成 ALTER TABLE SQL 语句时，列名会被直接拼接到 SQL 字符串中。
            如果列名包含恶意字符（如分号、引号），可能导致 SQL 注入攻击。
            通过正则白名单验证，确保列名仅包含安全的字母、数字和下划线。

        验证规则：
            1. 不能为空或非字符串类型
            2. 必须以字母或下划线开头
            3. 仅包含字母、数字、下划线

        Args:
            name: 待验证的列名

        Returns:
            bool: True 表示列名安全合法，False 表示不合法
        """
        if not name or not isinstance(name, str):
            return False
        return bool(self.COLUMN_NAME_PATTERN.match(name))

    def __init__(self, engine: Any = None) -> None:
        """
        初始化同步工具

        Args:
            engine: SQLAlchemy引擎实例。如果为None则从 app.db.database 导入默认引擎。
                允许显式传入引擎的原因：
                1. 单元测试时可传入测试引擎，避免影响生产数据库
                2. 多数据库场景下可指定目标引擎
                3. 避免循环导入（在 database.py 的 init_db 中调用时）
        """
        if engine is not None:
            self.engine = engine
        else:
            from app.db.database import engine as default_engine
            self.engine = default_engine
        # inspector 用于获取数据库的元信息：表列表、列信息、索引等
        self.inspector = inspect(self.engine)

    def get_model_columns(self, table_name: str, Base) -> List[Dict]:
        """
        获取ORM模型定义的列信息

        从 SQLAlchemy 的 Base.metadata 中读取指定表的列定义，
        这些是代码中定义的"期望"表结构。

        Args:
            table_name: 表名（对应 ORM 模型的 __tablename__）
            Base: SQLAlchemy 声明式基类，包含所有已注册的模型元数据

        Returns:
            List[Dict]: 列信息字典列表，每个字典包含：
                - name: 列名
                - type: 列类型（字符串形式，如 'VARCHAR(50)', 'INTEGER'）
                - nullable: 是否允许为空
                - default: 默认值（字符串形式）
                - primary_key: 是否主键
                - comment: 列注释
            如果表名不在 Base.metadata 中，返回空列表
        """
        if table_name not in Base.metadata.tables:
            return []

        table = Base.metadata.tables[table_name]
        columns = []

        for column in table.columns:
            col_info = {
                'name': column.name,
                'type': str(column.type),       # 将 SQLAlchemy 类型对象转为字符串，如 VARCHAR(50)
                'nullable': column.nullable,
                'default': str(column.default) if column.default else None,
                'primary_key': column.primary_key,
                'comment': column.comment or ''
            }
            columns.append(col_info)

        return columns

    def get_db_columns(self, table_name: str) -> List[Dict]:
        """
        获取数据库实际的列信息

        通过 SQLAlchemy inspector 查询数据库的系统表（如 information_schema），
        获取指定表在数据库中的实际列定义。

        与 get_model_columns() 的区别：
            get_model_columns() 返回代码中定义的"期望"结构
            get_db_columns() 返回数据库中的"实际"结构
            两者的差异即为需要同步的内容

        Args:
            table_name: 表名

        Returns:
            List[Dict]: 列信息字典列表（格式同 get_model_columns）
            如果表不存在或查询失败，返回空列表
        """
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
            # 表不存在或权限不足时，inspector 会抛异常，返回空列表
            logger.warning(f"无法获取表 {table_name} 的列信息: {e}")
            return []

    def find_missing_columns(self, table_name: str, Base) -> Tuple[List[Dict], List[str]]:
        """
        检测ORM模型中有但数据库中缺失的列

        差异检测算法：
            1. 获取模型定义的列集合（get_model_columns）
            2. 获取数据库实际的列集合（get_db_columns）
            3. 用集合差集运算找出模型中有但数据库中没有的列
            即：missing = model_columns - db_columns

        注意：仅检测"缺失的列"，不检测类型变更、约束变更等，
        这是出于安全考虑——自动修改列类型可能导致数据丢失。

        Args:
            table_name: 表名
            Base: SQLAlchemy 声明式基类

        Returns:
            Tuple[List[Dict], List[str]]:
                - 第一个元素：缺失的列信息列表（包含完整的列定义）
                - 第二个元素：数据库中已存在的列名列表（用于调试和日志）
        """
        model_cols = self.get_model_columns(table_name, Base)
        db_cols = self.get_db_columns(table_name)

        # 使用集合推导提取数据库中已存在的列名，用于差集计算
        db_col_names = {col['name'] for col in db_cols}
        # 筛选出模型中存在但数据库中不存在的列
        missing_cols = [col for col in model_cols if col['name'] not in db_col_names]

        return missing_cols, list(db_col_names)

    def generate_add_column_sql(self, table_name: str, col_info: Dict) -> str:
        """
        生成添加列的ALTER TABLE SQL语句

        根据列信息生成标准的 ALTER TABLE ADD COLUMN 语句，
        包含列类型、是否允许为空、默认值和注释。

        安全措施：
            在拼接 SQL 前调用 _validate_column_name() 验证列名，
            防止恶意列名导致的 SQL 注入攻击。
            注意：table_name 未做验证是因为它来自 Base.metadata（可信来源），
            而列名理论上可能被篡改（如通过动态模型定义）。

        Args:
            table_name: 表名
            col_info: 列信息字典，包含 name/type/nullable/default/comment

        Returns:
            str: 完整的 ALTER TABLE SQL 语句

        Raises:
            ValueError: 列名未通过安全验证时抛出
        """
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
        """
        同步单个表的结构 - 检测差异并可选自动修复

        执行流程：
            1. 检测缺失列（find_missing_columns）
            2. 如果无缺失列 -> 状态设为 synced，直接返回
            3. 如果有缺失列 -> 状态设为 out_of_sync
            4. 如果 auto_fix=True -> 逐列生成并执行 ALTER TABLE SQL
            5. 根据修复结果更新状态：fixed / partial_fix / error

        auto_fix 参数的安全考量：
            auto_fix=True（默认）：
                自动执行 ALTER TABLE ADD COLUMN，适合应用启动时自动修复。
                风险：如果 ORM 模型定义有误，可能添加错误的列。
                缓解：仅做增量操作（添加列），不做破坏性操作。

            auto_fix=False：
                仅检测差异，不执行修复，适合以下场景：
                - CI/CD 流水线中的数据库一致性检查
                - 生产环境上线前的预检查
                - 需要人工审核后再修复的场景

        同步报告状态流转：
            synced      -> 无缺失列，表结构完全一致
            out_of_sync -> 有缺失列，但未修复（auto_fix=False）
            fixed       -> 所有缺失列已成功添加
            partial_fix -> 部分列添加成功，部分失败（继续执行，不中断）
            error       -> 同步过程发生异常（如表不存在）

        Args:
            table_name: 表名
            Base: SQLAlchemy 声明式基类
            auto_fix: 是否自动修复缺失的列（默认True）

        Returns:
            Dict: 同步结果报告，包含：
                - table: 表名
                - status: 同步状态（synced/out_of_sync/fixed/partial_fix/error）
                - missing_columns: 缺失的列名列表
                - fixed_columns: 已修复的列名列表
                - existing_columns: 数据库中已存在的列名列表（仅out_of_sync时有）
                - errors: 错误信息列表
        """
        result = {
            'table': table_name,
            'status': 'ok',
            'missing_columns': [],
            'fixed_columns': [],
            'errors': []
        }

        try:
            missing_cols, existing_cols = self.find_missing_columns(table_name, Base)

            # 无缺失列，表结构完全一致
            if not missing_cols:
                result['status'] = 'synced'
                return result

            # 检测到缺失列，标记为不同步
            result['status'] = 'out_of_sync'
            result['missing_columns'] = [col['name'] for col in missing_cols]
            result['existing_columns'] = existing_cols

            logger.warning(f"表 {table_name} 缺少 {len(missing_cols)} 个字段: {[c['name'] for c in missing_cols]}")

            # auto_fix=False 时仅检测不修复，直接返回
            if not auto_fix:
                return result

            # 自动修复：逐列添加缺失的字段
            with self.engine.connect() as conn:
                for col in missing_cols:
                    try:
                        sql = self.generate_add_column_sql(table_name, col)
                        conn.execute(text(sql))
                        result['fixed_columns'].append(col['name'])
                        logger.info(f"✓ 已添加列: {table_name}.{col['name']}")
                    except Exception as e:
                        # 单列添加失败不中断整个同步流程，记录错误继续处理其他列
                        error_msg = f"添加列 {col['name']} 失败: {e}"
                        result['errors'].append(error_msg)
                        logger.error(f"✗ {error_msg}")

                conn.commit()

            # 根据修复结果更新状态
            if result['errors']:
                # 部分列修复成功，部分失败
                result['status'] = 'partial_fix'
            elif result['fixed_columns']:
                # 所有缺失列均已成功添加
                result['status'] = 'fixed'

        except Exception as e:
            # 同步过程发生异常（如表不存在、数据库连接断开等）
            result['status'] = 'error'
            result['errors'].append(str(e))
            logger.error(f"同步表 {table_name} 时出错: {e}")

        return result

    def sync_all_tables(self, Base, auto_fix: bool = True, exclude_tables: List[str] = None) -> Dict:
        """
        同步所有表的结构 - 遍历 Base.metadata 中的所有表并逐一同步

        执行流程：
            1. 获取 Base.metadata 中注册的所有表名
            2. 排除 exclude_tables 中指定的表
            3. 逐一调用 sync_table() 同步每张表
            4. 汇总各表同步结果，生成完整报告

        Args:
            Base: SQLAlchemy 声明式基类，包含所有已注册模型的元数据
            auto_fix: 是否自动修复缺失的列（默认True）
            exclude_tables: 要排除的表名列表，排除原因可能是：
                - 该表由外部系统管理，不应自动修改
                - 该表结构复杂，需要手动迁移
                - 该表是临时表，不需要同步

        Returns:
            Dict: 完整的同步报告，包含：
                - total_tables: 检查的表总数
                - synced: 状态为 synced 的表数量
                - out_of_sync: 状态为 out_of_sync 的表数量
                - fixed: 状态为 fixed 或 partial_fix 的表数量
                - errors: 状态为 error 或 partial_fix 的表数量
                - details: 各表的详细同步结果列表
                - summary: 人类可读的摘要字符串
        """
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

        # 获取所有 ORM 模型定义的表名
        model_tables = list(Base.metadata.tables.keys())
        report['total_tables'] = len(model_tables)

        for table_name in model_tables:
            # 跳过排除列表中的表
            if table_name in exclude_tables:
                continue

            result = self.sync_table(table_name, Base, auto_fix=auto_fix)
            report['details'].append(result)

            # 统计各状态的表数量
            status = result['status']
            if status == 'synced':
                report['synced'] += 1
            elif status == 'out_of_sync':
                report['out_of_sync'] += 1
            elif status == 'fixed':
                report['fixed'] += 1
            elif status == 'partial_fix':
                # partial_fix 同时计入 fixed 和 errors
                # fixed: 表示有列被成功修复
                # errors: 表示有列修复失败，需要关注
                report['fixed'] += 1
                report['errors'] += 1
            elif status == 'error':
                report['errors'] += 1

        # 生成人类可读的摘要信息
        fixed_count = sum(len(d.get('fixed_columns', [])) for d in report['details'])
        report['summary'] = (
            f"检查了 {report['total_tables']} 个表，"
            f"{report['synced']} 个已同步，"
            f"{report['fixed']} 个已修复，"
            f"共添加 {fixed_count} 个缺失字段"
        )

        return report


def smart_sync_database(Base, auto_fix: bool = True) -> Dict:
    """
    智能同步数据库结构的便捷函数

    创建 DatabaseSyncTool 实例并执行全表同步，是 init_db() 中调用的入口函数。
    封装了工具实例化和结果日志记录的细节，简化调用方式。

    Args:
        Base: SQLAlchemy 声明式基类
        auto_fix: 是否自动修复缺失的列（默认True）。
            设为 False 时仅检测差异并生成报告，不执行 ALTER TABLE，
            适用于 CI/CD 流水线中的数据库一致性预检查。

    Returns:
        Dict: 同步报告（格式同 DatabaseSyncTool.sync_all_tables 的返回值）

    使用示例:
        # 应用启动时自动修复
        from app.db.database import Base
        from app.db.smart_sync import smart_sync_database
        report = smart_sync_database(Base)
        print(report['summary'])

        # CI/CD 中仅检测不修复
        report = smart_sync_database(Base, auto_fix=False)
        if report['out_of_sync'] > 0:
            print("数据库表结构不一致，请执行迁移！")
    """
    tool = DatabaseSyncTool()
    report = tool.sync_all_tables(Base, auto_fix=auto_fix)

    # 根据同步结果记录不同级别的日志
    if report['fixed'] > 0 or report['out_of_sync'] > 0:
        # 有修复或检测到不同步，记录警告级别日志
        logger.warning(f"数据库同步完成: {report['summary']}")
        for detail in report['details']:
            if detail['status'] in ['fixed', 'partial_fix', 'out_of_sync']:
                logger.info(
                    f"表 {detail['table']}: "
                    f"修复了 {len(detail.get('fixed_columns', []))} 个字段"
                )
    else:
        # 所有表结构一致，记录信息级别日志
        logger.info("数据库检查完成: 所有表结构已同步")

    return report


if __name__ == "__main__":
    """
    命令行入口 - 手动执行数据库结构同步

    执行方式：
        python -m app.db.smart_sync

    输出内容：
        1. 同步报告（JSON格式，包含每张表的详细同步结果）
        2. 摘要信息（人类可读的统计摘要）

    使用场景：
        1. 开发者手动检查数据库表结构是否与ORM模型一致
        2. 部署前验证数据库迁移是否完整
        3. 排查因表结构不一致导致的运行时错误
    """
    from app.db.database import Base
    import json

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    print("=" * 70)
    print("智能数据库结构同步工具")
    print("=" * 70)

    report = smart_sync_database(Base, auto_fix=True)

    print("\n同步报告:")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    print("\n" + "=" * 70)
    print(report['summary'])
    print("=" * 70)
