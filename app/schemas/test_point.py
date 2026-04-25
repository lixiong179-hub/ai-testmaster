"""
测试点模块 Schema - 测试点提取/分析/管理的请求与响应模型

本模块定义了测试点全生命周期的数据契约，包括：

测试点Schema分层：
- TestPointBase: 测试点基础字段（模块/功能/描述/优先级）
- TestPointCreate: 创建测试点请求，继承Base并添加project_id
- TestPointUpdate: 更新测试点请求，所有字段可选
- TestPointResponse: 测试点响应模型，包含ID和时间戳

测试点操作Schema：
- TestPointExtractRequest: 从上传文件提取测试点请求
- TestPointAnalyzeRequest: AI分析测试点请求
- TestPointListRequest: 测试点列表查询请求（含分页和筛选）
- TestPointListResponse: 测试点列表分页响应

辅助Schema：
- AnalysisProgress: AI分析进度模型

与Model的对应关系：
- TestPoint系列 -> app.models.test_point.TestPoint
- TestPointExtractRequest -> 触发文件内容解析和AI提取流程
- AnalysisProgress -> 异步任务进度追踪
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime


class TestPointExtractRequest(BaseModel):
    """
    从上传文件提取测试点请求模型

    业务用途：基于已上传的项目文件（需求文档等），通过AI提取测试点
    对应API：POST /api/v1/test-points/extract
    """
    file_id: int = Field(..., description="项目文件 ID（必填）")  # 必填，指定从哪个文件提取测试点


class TestPointExtractFromUiRequest(BaseModel):
    """
    从UI原型屏幕提取测试点请求模型

    业务用途：基于已解析的UI原型屏幕，通过AI从ui_spec中提取测试点
    对应API：POST /api/v1/test-point/extract-from-ui

    三维提取策略：
        - 页面维度：每个screen的页面功能、区域结构
        - 可交互元素维度：按钮、输入框、链接等交互操作
        - 流程边维度：页面间跳转、导航关系
    """
    project_id: int = Field(..., description="项目ID（必填）")  # 必填，项目隔离
    ui_screen_ids: List[int] = Field(..., min_length=1, description="UI原型屏幕ID列表（至少1个）")  # 必填，指定从哪些屏幕提取
    iteration_id: Optional[int] = Field(None, description="关联迭代ID（可选）")  # 可选，关联迭代


class TestPointBase(BaseModel):
    """
    测试点基础模型

    业务用途：定义测试点的核心字段，作为TestPointCreate/TestPointResponse的公共父类
    验证规则：模块1-100字符，功能1-200字符，描述1-500字符，优先级1-3
    与Model映射：对应 TestPoint Model 的 module/function/point/priority/ai_prompt 字段
    """
    module: str = Field(..., min_length=1, max_length=100, description="模块名称")  # 必填，如"登录模块"/"支付模块"
    function: str = Field(..., min_length=1, max_length=200, description="功能名称")  # 必填，如"账号密码登录"/"微信支付"
    point: str = Field(..., min_length=1, max_length=500, description="测试点描述")  # 必填，如"输入错误密码登录"/"余额不足支付"
    priority: int = Field(..., ge=1, le=3, description="优先级：1高/2中/3低")  # 必填，1=高/2=中/3=低
    ai_prompt: Optional[str] = Field(None, description="AI分析时的提示词")  # 可选，引导AI生成更精准的测试用例


class TestPointCreate(TestPointBase):
    """
    创建测试点请求模型

    业务用途：手动创建或AI提取后创建测试点
    验证规则：继承TestPointBase，project_id必填
    对应API：POST /api/v1/test-points/
    与Model映射：project_id对应TestPoint.project_id外键
    """
    project_id: int = Field(..., description="项目ID")  # 必填，测试点所属项目，实现多项目隔离


class TestPointResponse(TestPointBase):
    """
    测试点响应模型

    业务用途：API返回测试点信息时使用
    对应API：GET /api/v1/test-points/{point_id}
    与Model映射：映射 TestPoint Model 的 id/project_id/create_time及Base中的所有字段
    """
    id: int  # 测试点主键ID，与TestPoint.id对应
    project_id: int  # 所属项目ID，与TestPoint.project_id对应
    requirement_id: Optional[int] = None  # 关联需求ID，历史数据允许为空
    create_time: datetime  # 创建时间，与TestPoint.create_time对应
    created_by: Optional[str] = None  # 创建人用户名
    test_case_count: int = 0  # 关联测试用例数量

    class Config:
        # 启用ORM模式，支持从TestPoint Model直接读取属性
        from_attributes = True


class TestPointAnalyzeRequest(BaseModel):
    """
    测试点分析请求模型

    业务用途：对项目中的测试点进行AI分析，优化测试点质量
    对应API：POST /api/v1/test-points/analyze
    """
    project_id: int = Field(..., description="项目ID")  # 必填，指定分析的项目


class TestPointListRequest(BaseModel):
    """
    测试点列表查询请求模型

    业务用途：分页查询测试点，支持按模块和优先级筛选
    验证规则：project_id必填，分页参数有边界约束
    对应API：GET /api/v1/test-points/
    """
    project_id: int = Field(..., description="项目ID")  # 必填，项目隔离查询
    module: Optional[str] = Field(None, description="模块名称")  # 可选，按模块筛选
    priority: Optional[int] = Field(None, ge=1, le=3, description="优先级")  # 可选，按优先级筛选
    created_by: Optional[str] = Field(None, description="创建人用户名")  # 可选，按创建人筛选
    requirement_id: Optional[int] = Field(None, description="关联需求ID")  # 可选，按需求筛选
    keyword: Optional[str] = Field(None, description="关键词，匹配模块/功能/测试点")  # 可选，模糊搜索
    created_from: Optional[date] = Field(None, description="创建开始日期")  # 可选，起始日期
    created_to: Optional[date] = Field(None, description="创建结束日期")  # 可选，结束日期
    sort_by: str = Field("create_time", description="排序字段")  # 默认按创建时间排序
    sort_order: str = Field("desc", description="排序方向：asc/desc")  # 默认倒序
    page: int = Field(1, ge=1, description="页码")  # 页码，默认第1页
    page_size: int = Field(10, ge=1, le=100, description="每页数量")  # 每页数量，默认10，最大100


class TestPointListResponse(BaseModel):
    """
    测试点列表分页响应模型

    业务用途：返回分页查询结果
    对应API：GET /api/v1/test-points/ 的响应
    """
    total: int  # 符合条件的测试点总数
    items: List[TestPointResponse]  # 当前页的测试点列表
    page: int  # 当前页码
    page_size: int  # 每页数量


class TestPointListStatsResponse(BaseModel):
    """测试点列表统计响应模型。"""

    total: int = Field(..., description="当前筛选条件下的测试点总数")
    high_priority_count: int = Field(..., description="高优先级测试点数量")
    medium_priority_count: int = Field(..., description="中优先级测试点数量")
    low_priority_count: int = Field(..., description="低优先级测试点数量")
    generated_case_count: int = Field(..., description="已生成关联用例总数")


class TestPointRequirementOptionResponse(BaseModel):
    """测试点筛选所需的需求选项。"""

    id: int = Field(..., description="需求ID")
    req_no: str = Field(..., description="需求编号")
    title: str = Field(..., description="需求标题")


class AnalysisProgress(BaseModel):
    """
    AI分析进度模型

    业务用途：追踪AI分析测试点的异步任务进度，通过WebSocket或轮询获取
    验证规则：进度0-100
    """
    progress: int = Field(..., ge=0, le=100, description="分析进度（0-100%）")  # 进度百分比，0=开始/100=完成
    message: str = Field(..., description="进度消息")  # 当前阶段的描述信息
    status: str = Field(..., description="分析状态")  # 如"processing"/"completed"/"failed"


class TestPointUpdate(BaseModel):
    """
    更新测试点请求模型 - 用于PUT接口

    业务用途：修改测试点信息，支持部分更新
    验证规则：所有字段可选，仅更新传入的字段
    对应API：PUT /api/v1/test-points/{point_id}
    """
    module: Optional[str] = Field(None, min_length=1, max_length=100, description="模块名称")  # 可选
    function: Optional[str] = Field(None, max_length=200, description="功能名称")  # 可选
    point: Optional[str] = Field(None, min_length=1, max_length=500, description="测试点描述")  # 可选
    priority: Optional[int] = Field(None, ge=1, le=3, description="优先级：1高/2中/3低")  # 可选
    ai_prompt: Optional[str] = Field(None, description="AI提示词")  # 可选


class TestPointXmindPreviewItem(BaseModel):
    """XMind 导入预览项。

    业务用途：XMind 文件解析后的单条测试点预览数据
    对应API：POST /api/v1/test-point/import-xmind (preview=true) 响应子项

    字段说明:
        - module: 必填，一级主题映射
        - function: 可选，二级主题映射（无子节点时可能为空）
        - point: 必填，三级主题映射
        - priority: 必填，1高/2中/3低
    """
    module: str = Field(..., min_length=1, max_length=100, description="模块名称")
    function: Optional[str] = Field(None, max_length=200, description="功能名称")
    point: str = Field(..., min_length=1, max_length=500, description="测试点描述")
    priority: int = Field(..., ge=1, le=3, description="优先级：1高/2中/3低")


class TestPointXmindPreviewCaseStep(BaseModel):
    """XMind 导入预览中的测试用例步骤。"""

    step_number: int = Field(..., ge=1, description="步骤序号")
    action: str = Field(..., min_length=1, description="操作步骤")
    expected_result: str = Field("", description="步骤预期结果")


class TestPointXmindPreviewCaseItem(BaseModel):
    """XMind 导入预览中的测试用例项。"""

    module: str = Field(..., min_length=1, max_length=100, description="模块名称")
    function: str = Field(..., min_length=1, max_length=200, description="功能名称")
    title: str = Field(..., min_length=1, max_length=255, description="用例标题")
    precondition: str = Field("", description="前置条件")
    expected_result: str = Field("", description="总体预期结果")
    priority: int = Field(..., ge=1, le=3, description="优先级：1高/2中/3低")
    step_count: int = Field(..., ge=0, description="步骤数")
    steps: List[TestPointXmindPreviewCaseStep] = Field(default_factory=list, description="步骤列表")


class TestPointXmindPreviewResponse(BaseModel):
    """XMind 导入预览响应模型。

    业务用途：预览模式下返回解析结果，不写入数据库
    对应API：POST /api/v1/test-point/import-xmind (preview=true)
    """
    preview_mode: str = Field("test_points", description="预览模式：test_points 或 test_cases")
    total: int = Field(..., description="解析出的测试点总数")
    items: List[TestPointXmindPreviewItem] = Field(..., description="测试点列表")
    case_total: int = Field(0, description="解析出的测试用例总数")
    case_items: List[TestPointXmindPreviewCaseItem] = Field(default_factory=list, description="测试用例列表")
    skipped_count: int = Field(0, description="跳过数量")
    skipped_reasons: List[str] = Field(default_factory=list, description="跳过原因列表")
    ai_timeout: bool = Field(False, description="AI增强模式是否因超时而降级")


class TestPointXmindImportResponse(BaseModel):
    """XMind 导入结果响应模型。

    业务用途：导入模式下返回写入结果统计
    对应API：POST /api/v1/test-point/import-xmind (preview=false)
    """
    saved_count: int = Field(..., description="成功保存数量")
    saved_case_count: int = Field(0, description="成功保存的测试用例数量")
    total_parsed: int = Field(..., description="解析总数")
    skipped_count: int = Field(0, description="跳过数量")
    skipped_reasons: List[str] = Field(default_factory=list, description="跳过原因列表")
    ai_timeout: bool = Field(False, description="AI增强模式是否因超时而降级")


class TestPointBatchGenerateRequest(BaseModel):
    """测试点批量生成测试用例请求模型。"""

    project_id: int = Field(..., description="项目ID")
    test_point_ids: List[int] = Field(..., min_length=1, description="测试点ID列表")
    case_type: Optional[str] = Field(None, description="用例类型，可选")


class TestPointRelatedCaseResponse(BaseModel):
    """测试点关联测试用例响应模型。"""

    id: int = Field(..., description="测试用例ID")
    case_no: str = Field(..., description="用例编号")
    title: str = Field(..., description="用例标题")
    module: str = Field(..., description="模块名称")
    priority: int = Field(..., description="优先级")
    case_type: Optional[str] = Field(None, description="用例类型")
    generate_status: int = Field(..., description="生成状态")
    create_time: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


class TestPointRelatedCaseListResponse(BaseModel):
    """测试点关联测试用例列表响应模型。"""

    total: int = Field(..., description="关联用例总数")
    items: List[TestPointRelatedCaseResponse] = Field(..., description="关联用例列表")
