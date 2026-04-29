"""
Bug缺陷管理模型模块

本模块定义了Bug缺陷（Bug）模型，用于跟踪和管理测试过程中发现的缺陷问题，
支持缺陷全生命周期管理（创建、指派、修复、关闭）。

核心类概览：
    - Bug : Bug缺陷模型，记录缺陷详情、严重程度和状态流转

表关系：
    Project → Bug（一对多，级联删除）
    User → Bug（一对多，报告人）
    User → Bug（一对多，指派人）
    TestCase → Bug（一对多，关联用例）
    TestResult → Bug（一对多，关联执行结果）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from datetime import datetime
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class Bug(Base):
    """
    Bug缺陷模型

    记录测试过程中发现的缺陷，包括缺陷描述、严重程度、优先级、
    状态流转和关联信息。支持从测试结果直接创建Bug。

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 多对一 → User（报告人）
        - 多对一 → User（指派人）
        - 多对一 → TestCase（关联测试用例）
        - 多对一 → TestResult（关联执行结果）

    使用场景：
        - 测试执行失败时自动创建Bug
        - Bug指派和状态流转管理
        - 按项目/严重程度/状态筛选Bug
    """
    __tablename__ = "bugs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # Bug主键ID
    bug_no = Column(String(50), nullable=False, unique=True, index=True, comment="Bug编号，如'BUG-2024-001'")  # Bug编号，全局唯一
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联项目ID")  # 项目ID，级联删除
    title = Column(String(255), nullable=False, comment="Bug标题")                                     # Bug标题，简要描述问题
    description = Column(Text, nullable=False, comment="Bug详细描述")                                  # Bug详细描述

    # 严重程度和优先级
    severity = Column(Integer, nullable=False, comment="严重程度: 1致命/2严重/3一般/4轻微")              # 1=致命，2=严重，3=一般，4=轻微
    priority = Column(Integer, nullable=False, comment="优先级：1高2中3低")                             # 1=高，2=中，3=低

    # 状态管理
    status = Column(String(20), nullable=False, default="open", comment="状态: open/in_progress/fixed/closed/rejected")  # open=待处理，in_progress=处理中，fixed=已修复，closed=已关闭，rejected=已拒绝

    # 人员分配
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="报告人ID")  # Bug报告人
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True, comment="指派给谁处理")  # Bug处理人

    # 关联信息
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=True, comment="关联测试用例ID")  # 关联的测试用例
    test_result_id = Column(Integer, ForeignKey("test_results.id"), nullable=True, comment="关联执行结果ID")  # 关联的测试执行结果

    # 复现信息
    reproduction_steps = Column(Text, nullable=True, comment="复现步骤")                               # 复现Bug的步骤
    expected_behavior = Column(Text, nullable=True, comment="预期行为")                                # 预期的正确行为
    actual_behavior = Column(Text, nullable=True, comment="实际行为")                                  # 实际的错误行为
    attachments = Column(Text, nullable=True, comment="附件路径（JSON数组格式）")                       # 附件文件路径列表

    # 时间信息
    create_time = Column(DateTime, nullable=False, default=utcnow, comment="创建时间")                  # 创建时间，UTC时区
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow, comment="更新时间")                 # 更新时间

    # 关联关系
    project = relationship("Project", backref="bugs")                                                 # 所属项目
    reporter = relationship("User", foreign_keys=[reporter_id])                                       # Bug报告人
    assignee = relationship("User", foreign_keys=[assignee_id])                                       # Bug处理人
    test_case = relationship("TestCase")                                                              # 关联测试用例
    test_result = relationship("TestResult")                                                          # 关联执行结果

    def __repr__(self):
        """返回Bug的字符串表示，便于调试和日志输出。"""
        return f"<Bug(id={self.id}, bug_no={self.bug_no}, title='{self.title}')>"
