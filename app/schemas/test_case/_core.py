from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from app.models.enums import TEST_CASE_LIFECYCLE_STATUS_PATTERN


class TestCaseStep(BaseModel):
    step: Union[str, int] = Field(..., description="步骤描述或编号")
    action: str = Field(..., description="操作")
    param: str = Field("", description="参数/预期结果")
    expected_result: Optional[str] = Field(None, description="预期结果")
    test_data: Optional[Dict[str, Any]] = Field(None, description="测试数据")
    description: Optional[str] = Field(None, description="步骤描述")
    ui_elements: Optional[List[str]] = Field(None, description="UI元素列表")
    action_type: Optional[str] = Field(None, description="操作类型：click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress")
    input_value: Optional[str] = Field(None, description="输入值（仅input类型步骤）")
    target_element: Optional[str] = Field(None, description="目标元素描述")

    model_config = {"extra": "allow"}


class TestCaseBase(BaseModel):
    case_no: str = Field("", min_length=0, max_length=50, description="用例编号（为空时自动生成）")
    module: str = Field("", min_length=0, max_length=100, description="模块名称")
    title: str = Field(..., min_length=1, max_length=255, description="用例标题")
    precondition: str = Field("", min_length=0, description="前置条件")
    steps: List[TestCaseStep] = Field(default_factory=list, description="可执行步骤")
    expected_result: str = Field("", min_length=0, description="预期结果")
    priority: int = Field(2, ge=1, le=3, description="优先级：1高/2中/3低")
    case_type: Optional[str] = Field(None, min_length=0, max_length=20, description="用例类型：ui_automation/manual/api_automation/performance/security")
    test_category: Optional[str] = Field(None, description="用例分类标签（与case_type保持一致）")
    exec_script: Optional[str] = Field(None, description="执行脚本")
    generate_status: int = Field(0, ge=0, le=2, description="生成状态：0生成中/1生成成功/2生成失败")
    lifecycle_status: str = Field("draft", pattern=TEST_CASE_LIFECYCLE_STATUS_PATTERN, description="生命周期状态：draft/active/pending_review/needs_modify/locator_broken/deprecated/archived")
    depends_on: Optional[str] = Field(None, max_length=255, description="依赖的主干用例标题")
    anchor_step: Optional[int] = Field(None, description="依赖主干用例的步骤号")
    fallback_steps: Optional[str] = Field(None, description="降级导航步骤JSON")
    setup_api_calls: Optional[str] = Field(None, description="API前置准备JSON")

    @field_validator('title', mode='before')
    @classmethod
    def _normalize_title(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
        return v


class TestCaseCreate(TestCaseBase):
    project_id: int = Field(..., description="项目ID")
    test_point_id: Optional[int] = Field(None, description="关联测试点ID")
    summary: Optional[str] = Field(None, description="AI生成的用例摘要")
    summary_model_version: Optional[str] = Field(None, description="生成摘要的AI模型版本")
    parent_case_id: Optional[int] = Field(None, description="父用例ID")
    depends_on: Optional[str] = Field(None, max_length=255, description="依赖的主干用例标题")
    anchor_step: Optional[int] = Field(None, description="依赖主干用例的步骤号")
    fallback_steps: Optional[str] = Field(None, description="降级导航步骤JSON")
    setup_api_calls: Optional[str] = Field(None, description="API前置准备JSON")
    ai_change_type: Optional[str] = Field(None, description="AI评审结果：added/modified/deprecated")
    test_data: Optional[Dict[str, Any]] = Field(None, description="用例级测试数据（normal/boundary/abnormal）")


class TestCaseResponse(TestCaseBase):
    id: int
    project_id: int
    test_point_id: Optional[int] = None
    summary: Optional[str] = None
    summary_version: int = 0
    summary_model_version: Optional[str] = None
    parent_case_id: Optional[int] = None
    ai_change_type: Optional[str] = None
    last_review_id: Optional[int] = None
    review_status: Optional[str] = None
    review_comment: Optional[str] = None
    reviewed_by: Optional[str] = None  # 审核人用户名
    reviewed_at: Optional[datetime] = None
    correction_status: Optional[str] = None
    prior_quality_score: Optional[float] = None
    posterior_quality_score: Optional[float] = None
    deprecated_at: Optional[datetime] = None
    depends_on: Optional[str] = None
    anchor_step: Optional[int] = None
    fallback_steps: Optional[str] = None
    setup_api_calls: Optional[str] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    update_time: Optional[datetime] = None
    create_time: datetime
    requirement_file_id: Optional[int] = None  # 关联需求文件ID

    @model_validator(mode='before')
    @classmethod
    def map_steps_json_to_steps(cls, data: Any) -> Any:
        """将ORM模型的steps_json字段映射为Schema的steps字段"""
        if hasattr(data, 'steps_json'):
            raw = getattr(data, 'steps_json', None)
            if raw is not None and not hasattr(data, 'steps'):
                object.__setattr__(data, 'steps', raw)
        elif isinstance(data, dict) and 'steps_json' in data and 'steps' not in data:
            data['steps'] = data.pop('steps_json')
        return data

    class Config:
        from_attributes = True


class TestCaseUpdate(TestCaseBase):
    case_no: Optional[str] = Field(None, min_length=0, max_length=50, description="用例编号（为空时自动生成）")
    module: Optional[str] = Field(None, min_length=0, max_length=100, description="模块名称")
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="用例标题")
    precondition: Optional[str] = Field(None, description="前置条件")
    expected_result: Optional[str] = Field(None, description="预期结果")
    priority: Optional[int] = Field(None, ge=1, le=3, description="优先级：1高/2中/3低")
    case_type: Optional[str] = Field(None, max_length=20, description="用例类型：ui_automation/manual/api_automation/performance/security")
    exec_script: Optional[str] = Field(None, description="执行脚本")
    generate_status: Optional[int] = Field(None, ge=0, le=2, description="生成状态：0生成中/1生成成功/2生成失败")
    lifecycle_status: Optional[str] = Field(None, pattern=TEST_CASE_LIFECYCLE_STATUS_PATTERN, description="生命周期状态")
    summary: Optional[str] = Field(None, description="AI生成的用例摘要")
    summary_model_version: Optional[str] = Field(None, description="生成摘要的AI模型版本")
    parent_case_id: Optional[int] = Field(None, description="父用例ID")


class TestCaseGenerateRequest(BaseModel):
    project_id: int = Field(..., description="项目ID")
    point_ids: Optional[List[int]] = Field(None, description="测试点ID列表，不指定则用所有测试点")


class TestCaseListRequest(BaseModel):
    project_id: int = Field(..., description="项目ID")
    module: Optional[str] = Field(None, description="模块名称")
    priority: Optional[int] = Field(None, ge=1, le=3, description="优先级")
    case_type: Optional[str] = Field(None, description="用例类型")
    generate_status: Optional[int] = Field(None, ge=0, le=2, description="生成状态")
    lifecycle_status: Optional[str] = Field(None, pattern=TEST_CASE_LIFECYCLE_STATUS_PATTERN, description="生命周期状态")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")


class TestCaseListResponse(BaseModel):
    total: int
    items: List[TestCaseResponse]
    page: int
    page_size: int


class TestCaseRetryRequest(BaseModel):
    project_id: int = Field(..., description="项目ID")


class TestCaseDeleteRequest(BaseModel):
    project_id: int = Field(..., description="项目ID")
