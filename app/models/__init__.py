"""
模型包初始化模块

本模块负责统一注册和导出所有数据模型，确保 SQLAlchemy 在应用启动时
能正确识别所有表及其关联关系。

导入顺序说明：
    - ui_prototype 必须最先导入，因为它定义了 ui_screen_test_case_links 关联表，
      而 test_case.py 中的 TestCase 模型通过 secondary 参数引用该关联表，
      若导入顺序颠倒会导致 NameError。

核心模型概览：
    - User / Role / Permission   : RBAC 用户-角色-权限体系
    - Project / ProjectFile      : 多项目隔离核心，所有业务数据通过 project_id 隔离
    - Iteration                  : 项目迭代管理
    - TestCase / TestStep        : 测试用例及步骤（含前置条件步骤）
    - TestPoint                  : 测试点（需求到用例的中间产物）
    - TestTask / TestResult      : 测试任务执行与结果记录
    - TestData                   : 测试步骤数据驱动
    - TestReport                 : 测试报告
    - UIPrototypeScreen          : UI原型屏幕（与用例多对多关联）
    - ElementLocator             : 元素定位器（UI自动化）
    - Requirement                : 需求管理
    - ApiCostLog / OperationLog  : API成本与操作审计日志
    - NLTestStep / TestCaseData  : 自然语言步骤与用例数据关联

表关系核心链路：
    User → Project → [TestCase, TestPoint, TestTask, Iteration, TestReport]
    TestCase → TestStep → [ElementLocator, TestData]
    TestTask → TestResult → TestCase
    UIPrototypeScreen ↔ TestCase（多对多）
"""
# 导入顺序很重要：ui_prototype 必须先导入，因为它定义了 ui_screen_test_case_links 关联表
# 而 test_case.py 中的 TestCase 模型需要引用这个关联表
from app.models.ui_prototype import UIPrototypeScreen, UIScreenTestCaseLink, UIPrototypeProject
from app.models.project_flow_data import ProjectFlowData
from app.models.iteration import Iteration, IterationInput
from app.models.pipeline import PipelineRun, PipelineStep, Artifact
from app.models.pipeline_metric import PipelineMetric
from app.models.project import Project, ProjectFile
from app.models.user import User, Role, Permission, UserRole
from app.models.element_locator import ElementLocator
from app.models.test_case import TestCase, TestStep, TestCaseExecution, TestCasePreconditionStep
from app.models.test_case_version import TestCaseVersion
from app.models.test_task import TestTask
from app.models.test_result import TestResult
from app.models.test_point import TestPoint
from app.models.test_capability import TestCapability
from app.models.report import TestReport
from app.models.test_data import TestData
from app.models.video_record import VideoRecord

# 核心业务模型
from app.models.requirement import Requirement
from app.models.requirement_link import RequirementLink
# from app.models.bug import Bug
# from app.models.group import Group, user_group, group_role
from app.models.code_review import CodeReview, ReviewItem, ReviewComment, ReviewMetric
# from app.models.resource_permission import ResourcePermission

# 辅助功能模型
from app.models.api_cost_log import ApiCostLog
from app.ai.call_log import AICallLog
from app.models.audit_log import AuditLog
from app.models.pipeline_config import PipelineConfig
from app.models.pipeline_permission import PipelineRole, PipelinePermission, pipeline_user_role
from app.models.operation_log import OperationLog
from app.models.nl_test_step import NLTestStep
from app.models.test_case_data import TestCaseData
from app.models.review import IterationReview, ReviewDecision, ReviewLock
from app.models.case_refresh_suggestion import CaseRefreshSuggestion
from app.models.ab_test_metric import ABTestMetric
from app.models.generation_batch import GenerationBatch, GenerationBatchSave

__all__ = [
    # UI原型相关
    "UIPrototypeScreen", "UIScreenTestCaseLink", "UIPrototypeProject",
    "ProjectFlowData",
    # 迭代管理
    "Iteration", "IterationInput",
    # Pipeline 存储
    "PipelineRun", "PipelineStep", "Artifact", "PipelineMetric",
    # 项目管理
    "Project",
    "ProjectFile",
    # 用户与权限（RBAC）
    "User", "Role", "Permission", "UserRole",
    # 元素定位（UI自动化）
    "ElementLocator",
    # 测试用例体系
    "TestCase", "TestStep", "TestCaseExecution", "TestCaseVersion", "TestCasePreconditionStep",
    # 测试执行体系
    "TestTask", "TestResult",
    # 测试点
    "TestPoint",
    # 业务能力
    "TestCapability",
    # 测试报告
    "TestReport",
    # 测试数据
    "TestData",
    # 视频录制
    "VideoRecord",
    # 需求管理
    "Requirement",
    "RequirementLink",
    # 代码评审
    "CodeReview", "ReviewItem", "ReviewComment", "ReviewMetric",
    # API成本日志
    "ApiCostLog",
    # AI调用日志（Pipeline）
    "AICallLog",
    # 审计日志（Pipeline）
    "AuditLog",
    # Pipeline 配置
    "PipelineConfig",
    # Pipeline 权限
    "PipelineRole",
    "PipelinePermission",
    "pipeline_user_role",
    # 操作审计日志
    "OperationLog",
    # 自然语言测试步骤
    "NLTestStep",
    # 测试用例数据关联
    "TestCaseData",
    "IterationReview", "ReviewDecision", "ReviewLock",
    "CaseRefreshSuggestion",
    # A/B测试指标
    "ABTestMetric",
    # 资料融合生成批次
    "GenerationBatch", "GenerationBatchSave",
]
