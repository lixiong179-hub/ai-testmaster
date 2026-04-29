"""
操作日志审计模型模块

本模块定义了操作日志（OperationLog）模型，用于记录用户操作行为，
支持安全审计和行为分析。

核心类概览：
    - OperationLog : 操作日志模型，记录用户操作详情

表关系：
    User → OperationLog（一对多）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from datetime import datetime
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class OperationLog(Base):
    """
    操作日志模型

    记录用户在系统中的操作行为，包括操作类型、资源对象、请求信息等，
    用于安全审计和行为分析。

    表关系：
        - 多对一 → User（操作用户）

    使用场景：
        - 用户操作审计和安全追溯
        - 异常行为检测和分析
        - 操作统计和用户行为分析
    """
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 日志主键ID

    # 操作用户
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="操作用户ID")  # 操作人ID

    # 操作信息
    operation_type = Column(String(50), nullable=False, comment="操作类型: create/update/delete/login/export/import")  # create=创建，update=更新，delete=删除，login=登录，export=导出，import=导入
    resource_type = Column(String(50), nullable=False, comment="资源类型: project/test_case/user/system")  # project=项目，test_case=用例，user=用户，system=系统
    resource_id = Column(Integer, nullable=True, comment="资源ID")                                    # 操作对象的ID
    action = Column(String(50), nullable=False, comment="具体动作描述")                                # 操作动作的详细描述

    # 请求信息
    ip_address = Column(String(50), nullable=True, comment="客户端IP地址")                             # 操作来源IP
    user_agent = Column(Text, nullable=True, comment="用户代理信息")                                   # 浏览器/客户端信息
    details = Column(Text, nullable=True, comment="操作详情（JSON格式）")                              # 操作的详细信息，JSON格式

    # 时间信息
    create_time = Column(DateTime, default=utcnow, comment="操作时间")                                 # 操作时间，UTC时区

    # 关联关系
    user = relationship("User", backref="operation_logs")                                             # 操作用户

    def __repr__(self) -> str:
        """返回操作日志的字符串表示，便于调试和日志输出。"""
        return f"<OperationLog(id={self.id}, user_id={self.user_id}, action='{self.action}')>"
