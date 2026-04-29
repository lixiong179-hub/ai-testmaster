"""
数据库时间工具模块

提供跨数据库的UTC时间处理，确保时区一致性。
在SQLAlchemy模型中推荐使用此模块的函数替代 datetime.utcnow()，
因为后者在Python 3.12+中已被弃用。

使用场景：
    - SQLAlchemy模型的default/onupdate参数
    - 数据库记录的时间戳字段
    - 任何需要与数据库交互的UTC时间获取

设计说明：
    返回naive datetime（无时区信息）而非aware datetime，
    是因为MySQL等数据库驱动不支持带时区的datetime对象。
    通过先获取timezone-aware时间再移除tzinfo，既保证了
    时间的正确性，又保证了数据库兼容性。
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """返回当前UTC时间（naive datetime，无时区信息，兼容MySQL）

    使用timezone-aware方式获取时间后移除时区信息，替代已弃用的datetime.utcnow()。
    确保在所有数据库驱动中都能正常存储。

    Returns:
        datetime: 无时区信息的当前UTC时间
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
