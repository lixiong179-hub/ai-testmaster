"""
自然语言测试步骤模型模块

本模块定义了自然语言测试步骤（NLTestStep）模型，用于存储自然语言形式的
测试步骤，支持AI驱动的测试执行。与TestStep不同，这里存储的是人类可读的
自然语言描述，由AI解释并执行。

核心类概览：
    - NLTestStep : 自然语言测试步骤模型

表关系：
    TestTask → NLTestStep（一对多）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from datetime import datetime
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import relationship
from app.db.database import Base


class NLTestStep(Base):
    """
    自然语言测试步骤模型

    存储自然语言形式的测试步骤，与结构化的TestStep不同，
    NLTestStep使用人类可读的自然语言描述操作目标、参数和预期结果，
    由AI引擎解释并执行。

    表关系：
        - 多对一 → TestTask（所属任务）

    使用场景：
        - AI驱动的自然语言测试执行
        - 记录AI执行每一步的操作和结果
        - 执行失败时的AI智能分析
    """
    __tablename__ = "nl_test_steps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 步骤主键ID

    # 关联信息
    task_id = Column(Integer, ForeignKey("test_tasks.id"), nullable=False, index=True, comment="关联任务ID")  # 所属任务ID

    # 步骤基本信息
    step_index = Column(Integer, nullable=False, comment="步骤序号")                                   # 步骤执行顺序
    action = Column(String(20), nullable=False, comment="操作类型: click/input/wait/assert/navigate")  # click=点击，input=输入，wait=等待，assert=断言，navigate=导航
    target_desc = Column(Text, nullable=False, comment="目标元素描述（自然语言）")                       # 目标元素的自然语言描述，如"登录按钮"
    param = Column(Text, nullable=True, comment="操作参数")                                            # 操作参数值，如输入框的文本
    expected = Column(Text, nullable=True, comment="预期结果")                                         # 步骤预期结果

    # 执行状态
    status = Column(String(20), nullable=True, comment="执行状态: pending/success/failed/skipped")     # pending=待执行，success=成功，failed=失败，skipped=跳过
    screenshot_path = Column(String(500), nullable=True, comment="截图路径")                           # 执行截图文件路径
    error_message = Column(Text, nullable=True, comment="错误信息")                                    # 执行失败时的错误信息

    # AI分析
    ai_analysis = Column(Text, nullable=True, comment="AI智能分析结果")                                # AI对执行结果的分析

    # 时间信息
    start_time = Column(DateTime, nullable=True, comment="开始时间")                                   # 步骤开始执行时间
    end_time = Column(DateTime, nullable=True, comment="结束时间")                                     # 步骤结束执行时间
    create_time = Column(DateTime, default=utcnow, server_default=text('CURRENT_TIMESTAMP'), comment="创建时间")  # 创建时间

    # 关联关系
    test_task = relationship("TestTask", backref="nl_test_steps")                                     # 所属任务

    def __repr__(self) -> str:
        """返回自然语言步骤的字符串表示，便于调试和日志输出。"""
        return f"<NLTestStep(id={self.id}, task_id={self.task_id}, step_index={self.step_index})>"
