"""
模型枚举定义模块

本模块定义了模型层共用的枚举类型，集中管理状态值和类型常量，
避免在业务层硬编码字符串值。

核心枚举概览：
    - LocatorStatus : 元素定位状态枚举
    - CapabilityStatus : 业务能力状态枚举
    - TestPointStatus : 测试点状态枚举
    - TestCaseLifecycleStatus : 测试用例生命周期状态枚举

使用场景：
    - ElementLocator.locator_status 字段引用
    - TestStep.locator_status 字段引用
    - TestCasePreconditionStep.locator_status 字段引用
    - TestCapability.status 字段引用
    - TestPoint.status 字段引用
    - TestCase.lifecycle_status 字段引用
"""
from enum import Enum


class LocatorStatus(str, Enum):
    """
    元素定位状态枚举

    定义UI自动化元素定位的三种状态，用于标记定位器的当前状态。

    Attributes:
        PENDING : 待定位，尚未尝试定位
        RECORDED : 已记录，定位信息已成功记录
        FAILED : 定位失败，无法获取有效的定位信息
    """
    PENDING = "pending"       # 待定位
    RECORDED = "recorded"     # 已记录
    FAILED = "failed"         # 定位失败


# CapabilityStatus 的合法值，用于 schema pattern 校验
CAPABILITY_STATUS_PATTERN = r"^(active|deprecated|archived)$"


class CapabilityStatus(str, Enum):
    """
    业务能力状态枚举

    定义业务能力的三种生命周期状态，用于 TestCapability.status 字段。

    Attributes:
        ACTIVE : 活跃，当前正在使用的业务能力
        DEPRECATED : 已废弃，不再推荐使用但保留兼容
        ARCHIVED : 已归档，终态不可恢复
    """
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


# TestPointStatus 的合法值，用于 schema pattern 校验
TEST_POINT_STATUS_PATTERN = r"^(draft|active|deprecated|archived)$"


class TestPointStatus(str, Enum):
    """
    测试点状态枚举

    定义测试点的四种生命周期状态，用于 TestPoint.status 字段。

    Attributes:
        DRAFT : 草稿，AI提取后待确认
        ACTIVE : 活跃，已确认的测试点
        DEPRECATED : 已废弃，不再推荐使用
        ARCHIVED : 已归档，终态
    """
    DRAFT = "draft"           # 草稿
    ACTIVE = "active"         # 活跃
    DEPRECATED = "deprecated" # 已废弃
    ARCHIVED = "archived"     # 已归档


# TestCaseLifecycleStatus 的合法值，用于 schema pattern 校验
TEST_CASE_LIFECYCLE_STATUS_PATTERN = r"^(draft|active|pending_review|needs_modify|locator_broken|deprecated|archived)$"


class TestCaseLifecycleStatus(str, Enum):
    """
    测试用例生命周期状态枚举

    定义测试用例的七种生命周期状态，用于 TestCase.lifecycle_status 字段。
    状态变更必须通过 LifecycleService，禁止直接 SQL update。

    Attributes:
        DRAFT : 草稿，AI生成后待确认
        ACTIVE : 活跃，已确认的测试用例
        PENDING_REVIEW : 待审核，提交审核中
        NEEDS_MODIFY : 需修改，审核未通过需修改
        LOCATOR_BROKEN : 定位失效，UI变更导致元素定位失败
        DEPRECATED : 已废弃，不再推荐使用
        ARCHIVED : 已归档，终态
    """
    DRAFT = "draft"                     # 草稿
    ACTIVE = "active"                    # 活跃
    PENDING_REVIEW = "pending_review"    # 待审核
    NEEDS_MODIFY = "needs_modify"        # 需修改
    LOCATOR_BROKEN = "locator_broken"    # 定位失效
    DEPRECATED = "deprecated"            # 已废弃
    ARCHIVED = "archived"                # 已归档


# IterationPipelineStatus 的合法值，用于 schema pattern 校验
ITERATION_PIPELINE_STATUS_PATTERN = r"^(draft|in_pipeline|in_review|finalized|archived)$"


class IterationPipelineStatus(str, Enum):
    """
    迭代流水线状态枚举

    定义迭代在流水线上下文中的五种状态，用于 Iteration.status 字段。
    状态由系统自动驱动，不由用户手动设置：
    draft → in_pipeline（Pipeline 启动时）→ in_review（Pipeline 完成时）→ finalized（评审 finalize 时）

    Attributes:
        DRAFT : 草稿，迭代已创建但未启动 Pipeline
        IN_PIPELINE : 流水线运行中
        IN_REVIEW : 评审中，Pipeline 完成后等待人工确认
        FINALIZED : 已定稿，评审已 finalize
        ARCHIVED : 已归档
    """
    DRAFT = "draft"                     # 草稿
    IN_PIPELINE = "in_pipeline"         # 流水线运行中
    IN_REVIEW = "in_review"             # 评审中
    FINALIZED = "finalized"             # 已定稿
    ARCHIVED = "archived"               # 已归档


# IterationInputKind 的合法值
ITERATION_INPUT_KIND_PATTERN = r"^(prd|prototype|xmind|testpoint|supplement_form)$"


class IterationInputKind(str, Enum):
    """
    迭代输入类型枚举

    定义流水线输入的五种类型，用于 IterationInput.kind 字段。

    Attributes:
        PRD : 需求文档
        PROTOTYPE : UI原型
        XMIND : XMind思维导图
        TESTPOINT : 测试点
        SUPPLEMENT_FORM : 补充表单（JSON payload）
    """
    PRD = "prd"                         # 需求文档
    PROTOTYPE = "prototype"             # UI原型
    XMIND = "xmind"                     # XMind思维导图
    TESTPOINT = "testpoint"             # 测试点
    SUPPLEMENT_FORM = "supplement_form" # 补充表单


class PipelineRunStatus(str, Enum):
    """
    Pipeline 运行状态枚举

    定义 PipelineRun 的 6 种状态，用于 pipeline_run.status 字段。

    Attributes:
        PENDING : 待执行
        RUNNING : 执行中
        WAITING_FOR_USER : 等待用户确认（confidence < 0.7）
        COMPLETED : 已完成
        FAILED : 执行失败
        CANCELLED : 已取消
    """
    PENDING = "pending"                    # 待执行
    RUNNING = "running"                    # 执行中
    WAITING_FOR_USER = "waiting_for_user"  # 等待用户确认
    COMPLETED = "completed"                # 已完成
    FAILED = "failed"                      # 执行失败
    CANCELLED = "cancelled"                # 已取消


class PipelineStepStatus(str, Enum):
    """
    Pipeline Step 状态枚举

    定义 PipelineStep 的 6 种状态，用于 pipeline_step.status 字段。

    Attributes:
        PENDING : 待执行
        RUNNING : 执行中
        DONE : 已完成
        FAILED : 执行失败
        SKIPPED : 已跳过
        DEGRADED : 降级完成（fallback 生效）
    """
    PENDING = "pending"    # 待执行
    RUNNING = "running"    # 执行中
    DONE = "done"          # 已完成
    FAILED = "failed"      # 执行失败
    SKIPPED = "skipped"    # 已跳过
    DEGRADED = "degraded"  # 降级完成
