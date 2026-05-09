"""
Alembic环境配置 - 数据库迁移自动化

功能：
1. 自动检测ORM模型变更
2. 生成迁移脚本
3. 支持版本回滚
4. 与项目配置集成

使用方法：
    # 生成新迁移
    alembic revision --autogenerate -m "描述"

    # 执行迁移
    alembic upgrade head

    # 回滚版本
    alembic downgrade -1
"""

import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入所有模型（确保Base.metadata包含所有表）
from app.db.database import Base

# 必须在导入config之前导入所有模型，否则autogenerate无法检测到模型变更
from app.models import user
from app.models import project
from app.models import test_data
from app.models import test_case
from app.models import test_task
from app.models import test_point
from app.models import test_result
from app.models import test_case_version
from app.models import element_locator
from app.models import ui_prototype
from app.models import requirement_link
from app.models import iteration
from app.models import report
from app.models import api_cost_log
from app.models import resource_permission
from app.models import requirement
from app.models import operation_log
from app.models import group
from app.models import nl_test_step
from app.models import code_review
from app.models import bug
from app.models import video_record
from app.models import test_case_data
from app.models import project_flow_data

# Alembic Config对象
config = context.config

# 设置Python路径（确保能找到app模块）
sys.path = ['', os.path.dirname(os.path.dirname(os.path.abspath(__file__)))] + sys.path[1:]

# 从日志配置文件解析日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 为'autogenerate'支持添加元数据目标
target_metadata = Base.metadata


def get_url():
    """从应用配置获取数据库URL"""
    from app.core.config import settings
    return settings.DATABASE_URL


def run_migrations_offline():
    """
    在'离线'模式下运行迁移。

    这只需要一个URL而不是Engine，
    虽然也接受Engine对象。
    通过将上下文声明为离线模式来调用。
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # 检测列类型变更
        compare_server_default=True,  # 检测默认值变更
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """
    在'在线'模式下运行迁移。

    通过创建引擎并关联连接来调用上下文。
    """
    # 使用可覆盖的配置字典
    configuration = config.get_section(config.config_ini_section, {})
    configuration['sqlalchemy.url'] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # 包含的表（可选，用于限制范围）
            # include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    """控制哪些对象应该被包含在迁移中"""
    # 排除某些临时表或视图（如果需要）
    if type_ == "table" and name.startswith("temp_"):
        return False
    return True


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
