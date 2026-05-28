"""
测试用例模型模块

本模块定义了测试用例的核心数据结构，包括用例主体、测试步骤、
前置条件步骤和用例执行记录，是测试管理体系的中心。

核心类概览：
    - TestCase                  : 测试用例主表，存储用例基本信息、审核状态和生成状态
    - TestStep                  : 测试步骤，支持业务视图和技术视图双重视角
    - TestCasePreconditionStep  : 前置条件步骤，将前置条件细化为可执行的技术步骤
    - TestCaseExecution         : 用例执行记录，记录每次执行的详细结果

表关系：
    Project → TestCase（一对多，级联删除）
    ProjectFile → TestCase（一对多，SET NULL，需求文件可删除但用例保留）
    TestCase → TestStep（一对多，级联删除）
    TestCase → TestCasePreconditionStep（一对多，级联删除）
    TestCase → TestCaseExecution（一对多，级联删除）
    TestCase → VideoRecord（一对多，级联删除）
    TestCase ←→ UIPrototypeScreen（多对多，通过 ui_screen_test_case_links 关联表）
    TestStep → ElementLocator（一对一，级联删除）
    TestStep → TestData（一对多，级联删除）
    TestTask → TestCaseExecution（一对多，SET NULL）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean, Float, event, Index
from sqlalchemy.orm import relationship, Session
from app.utils.db_time import utcnow
from app.db.database import Base
import contextvars


class TestCase(Base):
    """
    测试用例模型 - 可执行，与project_id强绑定

    存储测试用例的核心信息，包括用例编号、步骤、预期结果等。
    支持AI生成（generate_status）、人工审核（review_status）和
    自动纠正（correction_status）三种生命周期状态管理。

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 多对一 → ProjectFile（关联需求文件，SET NULL）
        - 一对多 → TestStep（测试步骤，级联删除）
        - 一对多 → TestCasePreconditionStep（前置条件步骤，级联删除）
        - 一对多 → TestCaseExecution（执行记录，级联删除）
        - 一对多 → VideoRecord（视频录制，级联删除）
        - 多对多 → UIPrototypeScreen（关联UI原型屏幕）

    使用场景：
        - AI根据需求文档自动生成测试用例
        - 人工审核和编辑用例
        - 执行测试任务时选取用例
        - 用例与UI原型关联，辅助UI自动化测试
    """
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                          # 用例主键ID
    case_no = Column(String(50), nullable=False, unique=True, comment="用例编号，如'PROJ1-CASE001'")   # 用例编号，全局唯一，格式为 项目前缀-CASE序号
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联项目ID，多项目隔离核心")  # 项目ID，级联删除
    requirement_file_id = Column(Integer, ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联需求文件ID，用于按需求筛选")  # 需求文件ID，SET NULL保留用例
    test_point_id = Column(Integer, ForeignKey("test_points.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联测试点ID")  # 测试点ID，兼容历史数据允许为空
    module = Column(String(100), nullable=False, comment="关联测试点模块")                             # 模块名称，与测试点的module对应
    title = Column(String(255), nullable=False, comment="用例标题")                                    # 用例标题，简要描述测试场景
    precondition = Column(Text, nullable=False, comment="前置条件")                                    # 前置条件文本描述
    steps_json = Column(JSON, nullable=False, comment="可执行步骤，格式：[{\"step\": \"步骤1\", \"action\": \"操作\", \"param\": \"参数\"}]")  # 步骤JSON，兼容旧版格式
    expected_result = Column(Text, nullable=False, comment="预期结果")                                 # 整体预期结果
    priority = Column(Integer, nullable=False, comment="优先级：1高/2中/3低")                          # 优先级，1=高优先级，2=中优先级，3=低优先级
    case_type = Column(String(20), nullable=False, comment="用例类型：API/UI/接口")                    # 用例类型，决定执行方式

    # 用例分类标签（支持多标签）
    # 取值：ui_automation=UI自动化测试, manual=手工测试, api_automation=接口自动化测试
    test_category = Column(String(100), nullable=True, comment="用例分类标签，多个用逗号分隔")            # 多标签，逗号分隔

    exec_script = Column(Text, nullable=True, comment="执行脚本占位，供后续测试模型调用")                # 预留字段，存储自动化执行脚本
    create_time = Column(DateTime, default=utcnow, nullable=False, comment="创建时间")                  # 创建时间，UTC时区
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow, comment="更新时间")                 # 更新时间
    generate_status = Column(Integer, nullable=False, default=0, comment="生成状态：0生成中/1生成成功/2生成失败")  # AI生成状态，0=生成中，1=成功，2=失败

    is_deleted = Column(Boolean, nullable=False, default=False, comment="软删除标记")                   # 软删除，True表示已删除
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")                                   # 软删除时间记录
    
    # 人工审核相关字段
    review_status = Column(String(20), default="pending", nullable=False, index=True, comment="审核状态：pending/approved/rejected/needs_optimization")  # pending=待审核，approved=已通过，rejected=已拒绝，needs_optimization=需优化
    review_comment = Column(Text, nullable=True, comment="审核意见")                                   # 审核人填写的意见
    reviewed_by = Column(String(100), nullable=True, comment="审核人")                                 # 审核人用户名
    reviewed_at = Column(DateTime, nullable=True, comment="审核时间")                                  # 审核操作时间

    correction_status = Column(String(30), default=None, nullable=True, index=True, comment="纠正状态：failed_correction/correcting/verifying/verified")  # failed_correction=纠正失败，correcting=纠正中，verifying=验证中，verified=已验证

    # 生命周期与血缘字段
    lifecycle_status = Column(String(30), nullable=False, default="draft", comment="生命周期状态：draft/active/pending_review/needs_modify/locator_broken/deprecated/archived")  # 生命周期状态，变更必经 LifecycleService
    prior_quality_score = Column(Float, nullable=True, comment="先验质量分（0-100），生成时由 QualityGate 计算")
    posterior_quality_score = Column(Float, nullable=True, comment="后验质量分（0-100），评审+执行后回填")
    deprecated_at = Column(DateTime, nullable=True, comment="进入deprecated状态的时间戳，用于冷却期计算")  # 由 LifecycleService.transition() 在进入 deprecated 时设置
    summary = Column(Text, nullable=True, comment="AI生成的用例摘要")  # AI摘要，用于去重和检索
    summary_version = Column(Integer, nullable=False, default=0, comment="摘要版本号，0=未生成")  # 摘要版本，AI重算时递增
    summary_model_version = Column(String(64), nullable=True, comment="生成摘要的AI模型版本")  # 跟踪模型升级触发的批量重算
    parent_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True, comment="父用例ID，用于用例衍生/拆分")  # 血缘关系，SET NULL保留子用例
    target_device = Column(String(20), nullable=True, comment="目标设备类型：tablet/phone/desktop/web，为空表示通用")
    migration_source_id = Column(Integer, ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True, comment="迁移来源用例ID，跨设备迁移时指向原设备用例")
    migration_type = Column(String(20), nullable=True, comment="迁移类型：cloned=直接克隆/adapted=AI改写/split=拆分迁移/new=新增/deprecated=废弃")
    migration_batch_id = Column(String(50), nullable=True, comment="迁移批次ID，同一次批量迁移产出的用例共享此ID，用于回退")
    ai_change_type = Column(String(20), nullable=True, comment="AI评审结果：added=查漏新增/modified=补缺修正/deprecated=去冗废弃")  # AI用例评审标注，手动创建的用例此字段为空
    depends_on = Column(String(255), nullable=True, comment="依赖的主干用例标题，UI自动化执行时先执行主干用例到anchor_step后继续")
    anchor_step = Column(Integer, nullable=True, comment="依赖主干用例的步骤号，从此步骤后继续执行本用例")
    fallback_steps = Column(Text, nullable=True, comment="降级导航步骤JSON，当主干快照不可用时执行此步骤序列到达目标页面")
    setup_api_calls = Column(Text, nullable=True, comment="API前置准备JSON，B端用例通过API直接创建数据状态，避免依赖UI快照")
    last_review_id = Column(Integer, ForeignKey("code_reviews.id", ondelete="SET NULL"), nullable=True, comment="最近一次评审ID")  # 关联评审记录

    __table_args__ = (
        Index("ix_test_cases_project_lifecycle", "project_id", "lifecycle_status"),
    )

    # 关联关系 - 通过project_id隔离
    project = relationship("Project", back_populates="test_cases")                                    # 所属项目
    test_point = relationship("TestPoint", backref="test_cases", foreign_keys=[test_point_id])        # 关联测试点
    parent_case = relationship("TestCase", remote_side=[id], foreign_keys=[parent_case_id], back_populates="child_cases")  # 父用例血缘关系
    child_cases = relationship("TestCase", back_populates="parent_case", foreign_keys=[parent_case_id])  # 子用例列表
    migration_source = relationship("TestCase", remote_side="TestCase.id", foreign_keys=[migration_source_id], lazy="select")
    last_review = relationship("CodeReview", foreign_keys=[last_review_id])  # 最近评审记录
    test_steps = relationship("TestStep", back_populates="test_case", cascade="all, delete-orphan")   # 测试步骤，级联删除
    precondition_steps = relationship("TestCasePreconditionStep", back_populates="test_case", cascade="all, delete-orphan", order_by="TestCasePreconditionStep.step_number")  # 前置条件步骤，按序号排序
    executions = relationship("TestCaseExecution", back_populates="test_case", cascade="all, delete-orphan")  # 执行记录，级联删除
    video_records = relationship("VideoRecord", back_populates="case", cascade="all, delete-orphan")  # 视频录制，级联删除

    # 多对多关联 - 与UI原型的关联（反向引用）
    linked_ui_screens = relationship(
        "UIPrototypeScreen",
        secondary="ui_screen_test_case_links",
        back_populates="linked_test_cases"
    )                                                                                                # 关联的UI原型屏幕，用于UI自动化定位


# ==================== lifecycle_status 保护机制 ====================
# contextvars 上下文标记：LifecycleService 执行迁移时设置，允许通过；其他途径修改则抛错
#
# 设计说明：
#   guard 注册在 Session 基类上（@event.listens_for(Session, "before_flush")），
#   因此所有 Session 实例都会触发拦截，包括业务 Session、迁移脚本、管理后台等。
#   非业务场景如需绕过 guard，必须显式调用 enable_lifecycle_transition() /
#   disable_lifecycle_transition()，确保意图明确可追溯。
#
# 使用 contextvars 而非 threading.local() 的原因：
#   FastAPI 异步模式下，同一线程内可能并发多个协程。threading.local() 在线程内
#   对所有协程共享，可能导致协程 A 开启了 lifecycle 许可，协程 B 绕过 guard。
#   contextvars 天然支持 asyncio 协程隔离，每个协程有独立的上下文副本。
#
# 批量操作逃生舱：
#   对于数据迁移、批量修复等场景，可使用 enable/disable 包裹批量操作：
#       enable_lifecycle_transition()
#       try:
#           for case in cases:
#               case.lifecycle_status = "active"
#           session.flush()
#       finally:
#           disable_lifecycle_transition()

_lifecycle_guard: contextvars.ContextVar[bool] = contextvars.ContextVar(
    'lifecycle_transition_allowed', default=False
)


def _lifecycle_transition_allowed() -> bool:
    """检查当前上下文是否允许修改 lifecycle_status（仅 LifecycleService 调用时为 True）。"""
    return _lifecycle_guard.get()


def enable_lifecycle_transition() -> None:
    """LifecycleService 调用前设置允许标记。"""
    _lifecycle_guard.set(True)


def disable_lifecycle_transition() -> None:
    """LifecycleService 调用后清除允许标记。"""
    _lifecycle_guard.set(False)


@event.listens_for(Session, "before_flush")
def _guard_lifecycle_status(session, flush_context, instances):
    """拦截 TestCase.lifecycle_status 的直接修改。

    如果 lifecycle_status 被修改且当前线程未通过 LifecycleService 授权，
    则抛出 RuntimeError，强制所有状态变更经过 LifecycleService.transition()。
    """
    for instance in session.dirty:
        if not isinstance(instance, TestCase):
            continue
        # 检查 lifecycle_status 是否被修改
        from sqlalchemy import inspect as sa_inspect
        state = sa_inspect(instance)
        hist = state.attrs.lifecycle_status.history
        if hist.deleted or hist.added:
            # lifecycle_status 被修改
            if not _lifecycle_transition_allowed():
                raise RuntimeError(
                    f"Direct update of TestCase.lifecycle_status is forbidden. "
                    f"Use LifecycleService.transition() instead. "
                    f"(case_id={instance.id}, "
                    f"old={hist.deleted[0] if hist.deleted else '?'}, "
                    f"new={hist.added[0] if hist.added else '?'})"
                )


class TestStep(Base):
    """
    测试步骤模型 - 支持业务视图和技术视图

    每个测试步骤支持双重视角展示：
    - 业务视图：面向测试人员，展示操作描述和预期结果
    - 技术视图：面向自动化工程师，展示元素定位、操作类型等技术细节

    表关系：
        - 多对一 → TestCase（所属用例，级联删除）
        - 一对一 → ElementLocator（元素定位器，级联删除）
        - 一对多 → TestData（测试数据，级联删除）

    使用场景：
        - 用例详情页展示步骤列表
        - UI自动化录制时记录元素定位
        - 数据驱动测试时绑定测试数据
    """
    __tablename__ = "test_steps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                           # 步骤主键ID
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)  # 所属用例ID，级联删除
    step_number = Column(Integer, nullable=False, comment="步骤序号")                                  # 步骤执行顺序，从1开始
    action = Column(Text, nullable=False, comment="操作步骤")                                         # 操作描述文本
    expected_result = Column(Text, nullable=False, comment="预期结果")                                 # 该步骤的预期结果
    create_time = Column(DateTime, default=utcnow, nullable=False)                                    # 创建时间
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow)                                   # 更新时间

    # 视图相关字段
    is_business_view = Column(Integer, default=1, nullable=False, comment="是否在业务视图显示：0隐藏/1显示")   # 控制业务视图可见性
    is_technical_view = Column(Integer, default=1, nullable=False, comment="是否在技术视图显示：0隐藏/1显示")  # 控制技术视图可见性

    # 元素定位相关字段（技术视图）
    has_locator = Column(Integer, default=0, nullable=False, comment="是否已记录元素定位：0否1是")       # 标记是否已完成元素定位
    locator_status = Column(String(20), default="pending", nullable=False, comment="定位状态：pending/recorded/failed")  # pending=待定位，recorded=已记录，failed=定位失败

    action_type = Column(String(20), nullable=True, comment="操作类型：click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress")  # 自动化操作类型
    input_value = Column(String(500), nullable=True, comment="输入值（仅input类型步骤）")               # 输入操作的值
    target_element = Column(String(200), nullable=True, comment="目标元素描述")                        # 被操作元素的自然语言描述

    # 关联关系
    test_case = relationship("TestCase", back_populates="test_steps")                                 # 所属用例
    element_locator = relationship("ElementLocator", back_populates="test_step", uselist=False, cascade="all, delete-orphan")  # 元素定位器，一对一
    test_data = relationship("TestData", back_populates="step", cascade="all, delete-orphan")         # 测试数据，一对多


class TestCasePreconditionStep(Base):
    """
    前置条件步骤模型 - 技术视图中将前置条件细化为可执行步骤

    将 TestCase.precondition 中的文本描述转化为结构化的可执行步骤，
    用于UI自动化测试的前置条件准备（如登录、导航到目标页面等）。

    表关系：
        - 多对一 → TestCase（所属用例，级联删除）
        - 一对一 → ElementLocator（元素定位器，级联删除）

    使用场景：
        - UI自动化执行前自动完成前置条件
        - 技术视图中编辑前置条件的技术细节
    """
    __tablename__ = "test_case_precondition_steps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                           # 前置步骤主键ID
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)  # 所属用例ID，级联删除
    step_number = Column(Integer, nullable=False, comment="步骤序号")                                  # 前置步骤执行顺序
    action = Column(Text, nullable=False, comment="操作步骤")                                         # 操作描述
    expected_result = Column(Text, nullable=False, default="", comment="预期结果")                     # 前置步骤预期结果，默认空字符串
    create_time = Column(DateTime, default=utcnow, nullable=False)                                    # 创建时间
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow)                                   # 更新时间

    # 元素定位相关字段（技术视图）
    has_locator = Column(Integer, default=0, nullable=False, comment="是否已记录元素定位：0否1是")       # 标记是否已完成元素定位
    locator_status = Column(String(20), default="pending", nullable=False, comment="定位状态：pending/recorded/failed")  # pending=待定位，recorded=已记录，failed=定位失败

    action_type = Column(String(20), nullable=True, comment="操作类型：click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress")  # 自动化操作类型
    input_value = Column(String(500), nullable=True, comment="输入值（仅input类型步骤）")               # 输入操作的值
    target_element = Column(String(200), nullable=True, comment="目标元素描述")                        # 被操作元素的自然语言描述

    # 关联关系
    test_case = relationship("TestCase", back_populates="precondition_steps")                         # 所属用例
    element_locator = relationship("ElementLocator", back_populates="precondition_step", uselist=False, cascade="all, delete-orphan")  # 元素定位器，一对一


class TestCaseExecution(Base):
    """
    测试用例执行记录模型

    记录测试用例在特定任务中的执行情况，包括执行状态、实际结果和时间信息。
    每次执行生成一条记录，支持同一用例的多次执行历史追溯。

    表关系：
        - 多对一 → TestCase（所属用例，级联删除）
        - 多对一 → TestTask（所属任务，SET NULL，任务删除后保留执行记录）

    使用场景：
        - 测试任务执行时记录每个用例的执行结果
        - 执行历史查询和趋势分析
        - 失败用例的排查和重试
    """
    __tablename__ = "test_case_executions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                           # 执行记录主键ID
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)  # 所属用例ID，级联删除
    test_task_id = Column(Integer, ForeignKey("test_tasks.id", ondelete="SET NULL"), nullable=True)   # 所属任务ID，SET NULL保留执行记录
    status = Column(String(20), default="pending", comment="执行状态：pending/running/passed/failed/blocked")
    actual_result = Column(Text, nullable=True, comment="实际执行结果")                                # 实际执行结果描述
    started_at = Column(DateTime, nullable=True, comment="开始执行时间")                               # 执行开始时间
    completed_at = Column(DateTime, nullable=True, comment="完成执行时间")                             # 执行完成时间
    create_time = Column(DateTime, default=utcnow, nullable=False)                                    # 记录创建时间

    # 关联关系
    test_case = relationship("TestCase", back_populates="executions")                                 # 所属用例
