"""
测试用例模块 Schema - 测试用例/步骤/技术视图/前置条件的请求与响应模型

本模块定义了测试用例全生命周期的数据契约，包括：

用例核心Schema分层：
- TestCaseStep: 测试用例步骤模型（嵌套结构，非Base/Create分层）
- TestCaseBase: 用例基础字段（编号/模块/标题/步骤/优先级等）
- TestCaseCreate: 创建用例请求，继承Base并添加project_id
- TestCaseUpdate: 更新用例请求，所有字段可选
- TestCaseResponse: 用例响应模型，包含ID和时间戳

用例操作Schema：
- TestCaseGenerateRequest: AI生成用例请求
- TestCaseListRequest: 用例列表查询请求（含分页和筛选）
- TestCaseListResponse: 用例列表分页响应
- TestCaseRetryRequest: 重试生成用例请求
- TestCaseDeleteRequest: 删除用例请求

技术视图Schema（用于元素定位和执行可视化）：
- TechnicalLocatorInfo: 元素定位信息（CSS/XPath/AI坐标等）
- TechnicalStepView: 技术视图步骤详情
- ExecutionHistoryItem: 执行历史记录
- TechnicalTestCaseView: 技术视图完整响应

前置条件步骤Schema：
- PreconditionStepCreate: 创建前置条件步骤
- PreconditionStepUpdate: 更新前置条件步骤
- PreconditionStepResponse: 前置条件步骤响应
- PreconditionStepBatchSave: 批量保存前置条件步骤

与Model的对应关系：
- TestCase系列 -> app.models.test_case.TestCase
- TestCaseStep -> TestCase.steps_json (JSON字段中的单个步骤)
- TechnicalLocatorInfo -> app.models.element_locator.ElementLocator
- PreconditionStep系列 -> app.models.test_case.TestCasePreconditionStep
- ExecutionHistoryItem -> app.models.test_case.TestCaseExecution
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Union, Literal
from datetime import datetime
from app.models.enums import TEST_CASE_LIFECYCLE_STATUS_PATTERN


class TestCaseStep(BaseModel):
    """
    测试用例步骤模型

    业务用途：定义用例中单个可执行步骤的完整信息，支持业务视图和技术视图
    验证规则：step和action必填，其他字段可选
    嵌套关系：被TestCaseBase.steps引用，作为步骤列表的单项
    与Model映射：对应 TestCase.steps_json JSON数组中的单个元素
    """
    step: Union[str, int] = Field(..., description="步骤描述或编号")  # 必填，步骤序号或描述，兼容字符串和整数
    action: str = Field(..., description="操作")  # 必填，具体操作描述，如"点击登录按钮"
    param: str = Field("", description="参数/预期结果")  # 操作参数，默认空字符串
    expected_result: Optional[str] = Field(None, description="预期结果")  # 可选，步骤级别的预期结果
    test_data: Optional[Dict[str, Any]] = Field(None, description="测试数据")  # 可选，步骤关联的测试数据键值对
    description: Optional[str] = Field(None, description="步骤描述")  # 可选，步骤补充说明
    ui_elements: Optional[List[str]] = Field(None, description="UI元素列表")  # 可选，步骤涉及的UI元素标识
    action_type: Optional[str] = Field(None, description="操作类型：click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress")  # 可选，用于技术视图的自动化执行
    input_value: Optional[str] = Field(None, description="输入值（仅input类型步骤）")  # 可选，仅当action_type=input时有效
    target_element: Optional[str] = Field(None, description="目标元素描述")  # 可选，操作的目标UI元素

    model_config = {"extra": "allow"}  # 允许额外字段，兼容AI生成步骤中可能出现的扩展属性


class TestCaseBase(BaseModel):
    """
    测试用例基础模型

    业务用途：定义测试用例的核心字段，作为TestCaseCreate/TestCaseResponse的公共父类
    验证规则：
        - 标题1-255字符（必填）
        - 优先级1-3（默认2中）
        - 生成状态0-2（默认0生成中）
    与Model映射：对应 TestCase Model 的 case_no/module/title/precondition/steps_json/expected_result/priority等字段
    """
    case_no: str = Field("", min_length=0, max_length=50, description="用例编号（为空时自动生成）")  # 默认空，服务端自动生成格式如PROJ1-CASE001
    module: str = Field("", min_length=0, max_length=100, description="模块名称")  # 默认空，关联测试点模块
    title: str = Field(..., min_length=1, max_length=255, description="用例标题")  # 必填，用例的核心描述
    precondition: str = Field("", min_length=0, description="前置条件")  # 默认空，执行前需满足的条件
    steps: List[TestCaseStep] = Field(default_factory=list, description="可执行步骤")  # 步骤列表，默认空列表
    expected_result: str = Field("", min_length=0, description="预期结果")  # 默认空，用例级别的预期结果
    priority: int = Field(2, ge=1, le=3, description="优先级：1高/2中/3低")  # 默认2（中），1=高/2=中/3=低
    case_type: Optional[str] = Field(None, min_length=0, max_length=20, description="用例类型：ui_automation/manual/api_automation/performance/security")  # 可选，区分自动化/手工/接口/性能/安全
    test_category: Optional[str] = Field(None, description="用例分类标签（与case_type保持一致）")  # 可选，与case_type语义一致，用于标签筛选
    exec_script: Optional[str] = Field(None, description="执行脚本")  # 可选，自动化执行脚本路径或内容
    generate_status: int = Field(0, ge=0, le=2, description="生成状态：0生成中/1生成成功/2生成失败")  # 默认0，AI生成用例的状态追踪
    lifecycle_status: str = Field("active", pattern=TEST_CASE_LIFECYCLE_STATUS_PATTERN, description="生命周期状态：draft/active/pending_review/needs_modify/locator_broken/deprecated/archived")  # 生命周期状态，变更必经 LifecycleService

    @field_validator('title', mode='before')
    @classmethod
    def _normalize_title(cls, v: str) -> str:
        """strip前后空格。空标题由 min_length=1 校验拒绝，兜底逻辑在 service 层。"""
        if isinstance(v, str):
            v = v.strip()
        return v


class TestCaseCreate(TestCaseBase):
    """
    创建测试用例请求模型

    业务用途：手动或AI生成创建测试用例
    验证规则：继承TestCaseBase，project_id必填
    对应API：POST /api/v1/test-cases/
    与Model映射：project_id对应TestCase.project_id外键
    """
    project_id: int = Field(..., description="项目ID")  # 必填，用例所属项目，实现多项目隔离
    test_point_id: Optional[int] = Field(None, description="关联测试点ID")  # 可选，关联测试点
    summary: Optional[str] = Field(None, description="AI生成的用例摘要")  # 可选，AI摘要
    summary_model_version: Optional[str] = Field(None, description="生成摘要的AI模型版本")  # 可选，AI模型版本
    parent_case_id: Optional[int] = Field(None, description="父用例ID")  # 可选，血缘关系


class TestCaseResponse(TestCaseBase):
    """
    测试用例响应模型

    业务用途：API返回用例信息时使用
    对应API：GET /api/v1/test-cases/{case_id}
    与Model映射：映射 TestCase Model 的 id/project_id/create_time及Base中的所有字段
    """
    id: int  # 用例主键ID，与TestCase.id对应
    project_id: int  # 所属项目ID，与TestCase.project_id对应
    test_point_id: Optional[int] = None  # 关联测试点ID
    summary: Optional[str] = None  # AI生成的用例摘要
    summary_version: int = 0  # 摘要版本号
    summary_model_version: Optional[str] = None  # 生成摘要的AI模型版本
    parent_case_id: Optional[int] = None  # 父用例ID
    last_review_id: Optional[int] = None  # 最近一次评审ID
    create_time: datetime  # 创建时间，与TestCase.create_time对应

    class Config:
        # 启用ORM模式，支持从TestCase Model直接读取属性
        from_attributes = True


class TestCaseGenerateRequest(BaseModel):
    """
    测试用例生成请求模型

    业务用途：基于测试点AI生成测试用例
    对应API：POST /api/v1/test-cases/generate
    """
    project_id: int = Field(..., description="项目ID")  # 必填，指定生成用例的目标项目
    point_ids: Optional[List[int]] = Field(None, description="测试点ID列表，不指定则用所有测试点")  # 可选，指定测试点则只生成对应用例


class TestCaseListRequest(BaseModel):
    """
    测试用例列表查询请求模型

    业务用途：分页查询测试用例，支持多维度筛选
    验证规则：project_id必填，分页参数有边界约束
    对应API：GET /api/v1/test-cases/
    """
    project_id: int = Field(..., description="项目ID")  # 必填，项目隔离查询
    module: Optional[str] = Field(None, description="模块名称")  # 可选，按模块筛选
    priority: Optional[int] = Field(None, ge=1, le=3, description="优先级")  # 可选，按优先级筛选
    case_type: Optional[str] = Field(None, description="用例类型")  # 可选，按类型筛选
    generate_status: Optional[int] = Field(None, ge=0, le=2, description="生成状态")  # 可选，按生成状态筛选
    lifecycle_status: Optional[str] = Field(None, pattern=TEST_CASE_LIFECYCLE_STATUS_PATTERN, description="生命周期状态")  # 可选，按生命周期状态筛选
    page: int = Field(1, ge=1, description="页码")  # 页码，默认第1页
    page_size: int = Field(10, ge=1, le=100, description="每页数量")  # 每页数量，默认10，最大100


class TestCaseListResponse(BaseModel):
    """
    测试用例列表分页响应模型

    业务用途：返回分页查询结果
    对应API：GET /api/v1/test-cases/ 的响应
    """
    total: int  # 符合条件的用例总数
    items: List[TestCaseResponse]  # 当前页的用例列表
    page: int  # 当前页码
    page_size: int  # 每页数量


class TestCaseRetryRequest(BaseModel):
    """
    测试用例重试生成请求模型

    业务用途：对生成失败的用例重新触发AI生成
    对应API：POST /api/v1/test-cases/retry
    """
    project_id: int = Field(..., description="项目ID")  # 必填，指定重试的项目


class TestCaseDeleteRequest(BaseModel):
    """
    测试用例删除请求模型

    业务用途：删除指定项目的测试用例
    对应API：DELETE /api/v1/test-cases/
    """
    project_id: int = Field(..., description="项目ID")  # 必填，指定删除的项目


class TestCaseUpdate(TestCaseBase):
    """
    更新测试用例请求模型

    业务用途：修改测试用例信息，支持部分更新
    验证规则：覆盖父类字段为Optional，仅更新传入的字段
    对应API：PUT/PATCH /api/v1/test-cases/{case_id}
    """
    case_no: Optional[str] = Field(None, min_length=0, max_length=50, description="用例编号（为空时自动生成）")  # 可选
    module: Optional[str] = Field(None, min_length=0, max_length=100, description="模块名称")  # 可选
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="用例标题")  # 可选
    precondition: Optional[str] = Field(None, description="前置条件")  # 可选
    expected_result: Optional[str] = Field(None, description="预期结果")  # 可选
    priority: Optional[int] = Field(None, ge=1, le=3, description="优先级：1高/2中/3低")  # 可选
    case_type: Optional[str] = Field(None, max_length=20, description="用例类型：ui_automation/manual/api_automation/performance/security")  # 可选
    exec_script: Optional[str] = Field(None, description="执行脚本")  # 可选
    generate_status: Optional[int] = Field(None, ge=0, le=2, description="生成状态：0生成中/1生成成功/2生成失败")  # 可选
    lifecycle_status: Optional[str] = Field(None, pattern=TEST_CASE_LIFECYCLE_STATUS_PATTERN, description="生命周期状态")  # 可选
    summary: Optional[str] = Field(None, description="AI生成的用例摘要")  # 可选
    summary_model_version: Optional[str] = Field(None, description="生成摘要的AI模型版本")  # 可选
    parent_case_id: Optional[int] = Field(None, description="父用例ID")  # 可选


# ==================== 技术视图相关Schema ====================

class TechnicalLocatorInfo(BaseModel):
    """
    技术视图 - 元素定位信息模型

    业务用途：存储UI元素的定位方式，用于自动化执行时定位页面元素
    与Model映射：对应 app.models.element_locator.ElementLocator 的关键字段
    """
    css_selector: Optional[str] = Field(None, description="CSS选择器")  # 可选，如"#login-btn"、".submit"
    xpath: Optional[str] = Field(None, description="XPath定位器")  # 可选，如"//button[@id='submit']"
    element_type: Optional[str] = Field(None, description="元素类型")  # 可选，如"button"/"input"/"link"
    ai_coordinate: Optional[Dict[str, float]] = Field(None, description="AI识别坐标")  # 可选，AI视觉定位的坐标，如{"x": 100.5, "y": 200.3}
    confidence: Optional[float] = Field(None, description="置信度")  # 可选，AI识别的置信度0-1
    locator_type: Optional[str] = Field(None, description="定位类型: css/xpath/id/name/ai")  # 可选，当前使用的定位方式
    locator_value: Optional[str] = Field(None, description="定位值")  # 可选，与locator_type配合使用的定位值


class TechnicalStepView(BaseModel):
    """
    技术视图 - 步骤详情模型

    业务用途：技术视图中展示步骤的定位状态和执行信息
    嵌套关系：被TechnicalTestCaseView引用，包含TechnicalLocatorInfo
    与Model映射：对应 TestStep Model 的技术视图字段
    """
    step_number: int = Field(..., description="步骤编号")  # 必填，步骤顺序
    action: str = Field(..., description="操作描述")  # 必填，操作内容
    expected_result: str = Field(..., description="预期结果")  # 必填，步骤预期结果
    has_locator: bool = Field(..., description="是否有定位信息")  # 是否已记录元素定位，影响自动化执行
    locator_status: str = Field(..., description="定位状态: pending/recorded/failed")  # pending=待定位/recorded=已定位/failed=定位失败
    locator: Optional[TechnicalLocatorInfo] = Field(None, description="定位详情")  # 可选，定位信息详情
    test_data: Optional[Dict[str, Any]] = Field(None, description="测试数据")  # 可选，步骤关联的测试数据


class ExecutionHistoryItem(BaseModel):
    """
    执行历史记录模型

    业务用途：展示用例的历次执行结果，用于趋势分析和问题定位
    与Model映射：对应 TestCaseExecution Model 的关键字段
    """
    execution_id: int = Field(..., description="执行ID")  # 执行记录主键
    execution_time: datetime = Field(..., description="执行时间")  # 执行发生的时间
    status: str = Field(..., description="执行状态: success/failed/running")  # 执行结果状态
    duration: Optional[float] = Field(None, description="执行时长(秒)")  # 可选，执行耗时
    error_message: Optional[str] = Field(None, description="错误信息")  # 可选，失败时的错误详情
    screenshot_url: Optional[str] = Field(None, description="截图URL")  # 可选，失败时的截图路径


class TechnicalTestCaseView(BaseModel):
    """
    技术视图完整响应模型

    业务用途：技术视图中展示用例的完整技术信息，包括定位覆盖率、步骤详情和执行历史
    对应API：GET /api/v1/test-cases/{case_id}/technical-view
    嵌套关系：包含TechnicalStepView列表、PreconditionStepResponse列表和ExecutionHistoryItem列表
    """
    case_id: int = Field(..., description="用例ID")  # 用例主键
    case_no: str = Field(..., description="用例编号")  # 用例编号，如PROJ1-CASE001
    title: str = Field(..., description="用例标题")  # 用例标题
    module: Optional[str] = Field(None, description="所属模块")  # 可选，模块名称
    precondition: Optional[str] = Field(None, description="前置条件")  # 可选，前置条件描述
    expected_result: Optional[str] = Field(None, description="整体预期结果")  # 可选，用例级别预期结果
    priority: Optional[int] = Field(None, description="优先级")  # 可选，1高/2中/3低
    case_type: Optional[str] = Field(None, description="用例类型")  # 可选，用例类型标签

    # 技术信息
    steps: List[TechnicalStepView] = Field(..., description="步骤列表")  # 必填，步骤的技术视图详情
    precondition_steps: List["PreconditionStepResponse"] = Field([], description="前置条件步骤列表")  # 前置条件步骤，默认空列表
    locator_coverage: float = Field(..., description="定位覆盖率")  # 已定位步骤数/总步骤数，0.0-1.0

    # 执行历史
    execution_history: List[ExecutionHistoryItem] = Field([], description="执行历史")  # 历次执行记录，默认空列表

    class Config:
        # 启用ORM模式，支持从Model直接读取属性
        from_attributes = True


# ==================== 前置条件步骤相关Schema ====================

class PreconditionStepCreate(BaseModel):
    """
    创建前置条件步骤模型

    业务用途：为测试用例创建前置条件步骤，将前置条件细化为可执行操作
    验证规则：step_number和action必填
    对应API：POST /api/v1/test-cases/{case_id}/precondition-steps
    与Model映射：对应 TestCasePreconditionStep Model 的关键字段
    """
    step_number: int = Field(..., description="步骤序号")  # 必填，步骤顺序
    action: str = Field(..., description="操作步骤")  # 必填，具体操作描述
    expected_result: str = Field("", description="预期结果")  # 默认空，步骤预期结果
    action_type: Optional[str] = Field(None, description="操作类型")  # 可选，如click/input/navigate
    input_value: Optional[str] = Field(None, description="输入值")  # 可选，仅input类型步骤
    target_element: Optional[str] = Field(None, description="目标元素描述")  # 可选，操作目标


class PreconditionStepUpdate(BaseModel):
    """
    更新前置条件步骤模型

    业务用途：修改前置条件步骤，支持部分更新
    对应API：PUT/PATCH /api/v1/test-cases/{case_id}/precondition-steps/{step_id}
    """
    step_number: Optional[int] = Field(None, description="步骤序号")  # 可选
    action: Optional[str] = Field(None, description="操作步骤")  # 可选
    expected_result: Optional[str] = Field(None, description="预期结果")  # 可选
    action_type: Optional[str] = Field(None, description="操作类型")  # 可选
    input_value: Optional[str] = Field(None, description="输入值")  # 可选
    target_element: Optional[str] = Field(None, description="目标元素描述")  # 可选


class PreconditionStepResponse(BaseModel):
    """
    前置条件步骤响应模型

    业务用途：API返回前置条件步骤信息时使用
    与Model映射：映射 TestCasePreconditionStep Model 的所有字段，含定位状态信息
    嵌套关系：被TechnicalTestCaseView引用，包含TechnicalLocatorInfo
    """
    id: int  # 步骤主键ID
    test_case_id: int  # 所属用例ID
    step_number: int  # 步骤序号
    action: str  # 操作描述
    expected_result: str  # 预期结果
    action_type: Optional[str] = None  # 操作类型，可能为空
    input_value: Optional[str] = None  # 输入值，可能为空
    target_element: Optional[str] = None  # 目标元素，可能为空
    has_locator: bool  # 是否已记录元素定位
    locator_status: str  # 定位状态：pending/recorded/failed
    locator: Optional[TechnicalLocatorInfo] = None  # 定位信息详情，可能为空

    class Config:
        # 启用ORM模式，支持从TestCasePreconditionStep Model直接读取属性
        from_attributes = True


class PreconditionStepBatchSave(BaseModel):
    """
    批量保存前置条件步骤模型

    业务用途：一次性保存用例的所有前置条件步骤，替代逐条创建
    对应API：POST /api/v1/test-cases/{case_id}/precondition-steps/batch
    """
    steps: List[PreconditionStepCreate] = Field(..., description="前置条件步骤列表")  # 必填，步骤列表


# ==================== 流程图排序相关Schema ====================

class FlowNodeSchema(BaseModel):
    """流程图节点Schema - 接收前端传递的排序数据

    业务用途：接收前端流程图编辑器中每个截图节点的排序和分类信息
    验证规则：screen_id/screen_order必填且>0，flow_type为枚举值
    与前端映射：对应 FlowNodeSubmitData 接口
    """
    screen_id: int = Field(..., gt=0, description="UI屏幕ID")
    screen_order: int = Field(..., gt=0, description="前端排序序号，从1开始")
    flow_type: Literal['main', 'branch', 'exception', 'bypass'] = Field(
        ..., description="流程类型：main=主干/branch=分支/exception=异常/bypass=旁路"
    )
    main_order: Optional[int] = Field(None, gt=0, description="主干显式顺序，仅main节点使用")
    screen_name: str = Field(..., min_length=1, max_length=200, description="屏幕名称")
    ocr_text: Optional[str] = Field(None, max_length=5000, description="OCR识别的页面文本")
    ui_spec_elements: Optional[List[Dict[str, Any]]] = Field(None, description="UI元素列表（从ui_spec提取）")
    summary: Optional[str] = Field(None, max_length=1000, description="AI解析摘要")

    @field_validator('screen_name')
    @classmethod
    def screen_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('screen_name不能为纯空白字符')
        return v.strip()


class FlowEdgeSchema(BaseModel):
    """流程图连线Schema - 接收前端传递的连线关系

    业务用途：接收前端流程图编辑器中节点间的连线关系和条件
    验证规则：source/target必填，edge_type为枚举值
    与前端映射：对应 FlowEdgeSubmitData 接口
    """
    source: str = Field(..., min_length=1, description="源节点screen_id的字符串形式")
    target: str = Field(..., min_length=1, description="目标节点screen_id的字符串形式")
    edge_type: Literal['normal', 'branch', 'exception', 'bypass'] = Field(
        ..., description="连线类型：normal=正常/branch=分支/exception=异常/bypass=旁路"
    )
    condition: Optional[str] = Field(None, max_length=500, description="触发条件/异常场景")
    label: str = Field(..., min_length=1, max_length=100, description="连线显示标签")

    @field_validator('label')
    @classmethod
    def label_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('label不能为纯空白字符')
        return v.strip()

    @model_validator(mode='after')
    def validate_condition_for_special_edges(self) -> 'FlowEdgeSchema':
        if self.edge_type != 'normal' and not (self.condition or '').strip():
            label_map = {
                'branch': '触发条件',
                'exception': '异常场景',
                'bypass': '出现时机',
            }
            raise ValueError(f"{label_map.get(self.edge_type, '条件')}不能为空")
        if self.condition is not None:
            self.condition = self.condition.strip()
        return self


class FlowSortDataSchema(BaseModel):
    """流程图排序完整数据Schema

    业务用途：接收前端流程图编辑器输出的完整排序数据
    验证规则：nodes至少1个，edges可为空
    与前端映射：对应 FlowSortSubmitData 接口
    """
    nodes: List[FlowNodeSchema] = Field(..., min_length=1, description="节点列表")
    edges: List[FlowEdgeSchema] = Field(default_factory=list, description="连线列表")
    module_info: Optional[Dict[str, Any]] = Field(None, description="模块基础信息")
