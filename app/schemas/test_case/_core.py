import json

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any
from datetime import datetime
from app.models.enums import TEST_CASE_LIFECYCLE_STATUS_PATTERN


class TestCaseStep(BaseModel):
    __test__ = False
    step: str | int = Field(..., description="步骤描述或编号")
    action: str = Field(..., description="操作")
    param: str = Field("", description="参数/预期结果")
    expected_result: str | None = Field(None, description="预期结果")
    test_data: dict[str, Any] | list[dict[str, Any]] | None = Field(None, description="测试数据")
    description: str | None = Field(None, description="步骤描述")
    ui_elements: list[str | dict[str, Any]] | None = Field(None, description="UI元素列表")
    action_type: str | None = Field(
        None, description="操作类型：click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress"
    )
    input_value: str | None = Field(None, description="输入值（仅input类型步骤）")
    target_element: str | None = Field(None, description="目标元素描述")

    model_config = {"extra": "allow"}


class TestCaseBase(BaseModel):
    __test__ = False
    case_no: str = Field("", min_length=0, max_length=50, description="用例编号（为空时自动生成）")
    module: str = Field("", min_length=0, max_length=100, description="模块名称")
    title: str = Field(..., min_length=1, max_length=255, description="用例标题")
    precondition: str = Field("", min_length=0, description="前置条件")
    steps: list[TestCaseStep] = Field(default_factory=list, description="可执行步骤")
    expected_result: str = Field("", min_length=0, description="预期结果")
    priority: int = Field(2, ge=1, le=3, description="优先级：1高/2中/3低")
    case_type: str | None = Field(
        None,
        min_length=0,
        max_length=20,
        description="用例类型：ui_automation/manual/api_automation/performance/security",
    )
    test_category: str | None = Field(None, description="用例分类标签（与case_type保持一致）")
    exec_script: str | None = Field(None, description="执行脚本")
    generate_status: int = Field(0, ge=0, le=2, description="生成状态：0生成中/1生成成功/2生成失败")
    lifecycle_status: str = Field(
        "draft",
        pattern=TEST_CASE_LIFECYCLE_STATUS_PATTERN,
        description="生命周期状态：draft/active/pending_review/needs_modify/locator_broken/deprecated/archived",
    )
    depends_on: str | None = Field(None, max_length=255, description="依赖的主干用例标题")
    anchor_step: int | None = Field(None, description="依赖主干用例的步骤号")
    fallback_steps: str | None = Field(None, description="降级导航步骤JSON")
    setup_api_calls: str | None = Field(None, description="API前置准备JSON")
    target_device: str | None = Field(None, max_length=20, description="目标设备类型：tablet/phone/desktop/web")

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
        return v


class TestCaseCreate(TestCaseBase):
    __test__ = False
    project_id: int = Field(..., description="项目ID")
    test_point_id: int | None = Field(None, description="关联测试点ID")
    summary: str | None = Field(None, description="AI生成的用例摘要")
    summary_model_version: str | None = Field(None, description="生成摘要的AI模型版本")
    parent_case_id: int | None = Field(None, description="父用例ID")
    depends_on: str | None = Field(None, max_length=255, description="依赖的主干用例标题")
    anchor_step: int | None = Field(None, description="依赖主干用例的步骤号")
    fallback_steps: str | None = Field(None, description="降级导航步骤JSON")
    setup_api_calls: str | None = Field(None, description="API前置准备JSON")
    ai_change_type: str | None = Field(None, description="AI评审结果：added/modified/deprecated")
    test_data: dict[str, Any] | None = Field(None, description="用例级测试数据（normal/boundary/abnormal）")
    migration_source_id: int | None = Field(None, description="迁移来源用例ID")
    migration_type: str | None = Field(None, max_length=20, description="迁移类型：cloned/adapted/split/new/deprecated")
    migration_batch_id: str | None = Field(None, max_length=50, description="迁移批次ID")


class TestCaseResponse(TestCaseBase):
    id: int
    project_id: int
    test_point_id: int | None = None
    summary: str | None = None
    summary_version: int = 0
    summary_model_version: str | None = None
    parent_case_id: int | None = None
    target_device: str | None = None
    migration_source_id: int | None = None
    migration_type: str | None = None
    migration_batch_id: str | None = None
    ai_change_type: str | None = None
    last_review_id: int | None = None
    review_status: str | None = None
    review_comment: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    correction_status: str | None = None
    prior_quality_score: float | None = None
    posterior_quality_score: float | None = None
    deprecated_at: datetime | None = None
    depends_on: str | None = None
    anchor_step: int | None = None
    fallback_steps: str | None = None
    setup_api_calls: str | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None
    update_time: datetime | None = None
    create_time: datetime
    requirement_file_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def map_steps_json_to_steps(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "steps" not in data and "steps_json" in data:
                mapped = dict(data)
                mapped["steps"] = cls._normalize_steps_json(mapped.get("steps_json"))
                return mapped
            return data

        if hasattr(data, "steps_json") and not hasattr(data, "steps"):
            mapped = {}
            for name in cls.model_fields:
                if name == "steps":
                    mapped[name] = cls._normalize_steps_json(getattr(data, "steps_json", None))
                elif hasattr(data, name):
                    mapped[name] = getattr(data, name)
            return mapped

        return data

    @staticmethod
    def _normalize_steps_json(raw: Any) -> list[dict[str, Any]]:
        if raw is None:
            return []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
        if not isinstance(raw, list):
            return []

        from app.utils.test_case_helpers import convert_steps_to_response

        return convert_steps_to_response(raw)

    class Config:
        from_attributes = True


class TestCaseUpdate(TestCaseBase):
    __test__ = False
    case_no: str | None = Field(None, min_length=0, max_length=50, description="用例编号（为空时自动生成）")
    module: str | None = Field(None, min_length=0, max_length=100, description="模块名称")
    title: str | None = Field(None, min_length=1, max_length=255, description="用例标题")
    precondition: str | None = Field(None, description="前置条件")
    expected_result: str | None = Field(None, description="预期结果")
    priority: int | None = Field(None, ge=1, le=3, description="优先级：1高/2中/3低")
    case_type: str | None = Field(
        None, max_length=20, description="用例类型：ui_automation/manual/api_automation/performance/security"
    )
    exec_script: str | None = Field(None, description="执行脚本")
    generate_status: int | None = Field(None, ge=0, le=2, description="生成状态：0生成中/1生成成功/2生成失败")
    lifecycle_status: str | None = Field(None, pattern=TEST_CASE_LIFECYCLE_STATUS_PATTERN, description="生命周期状态")
    summary: str | None = Field(None, description="AI生成的用例摘要")
    summary_model_version: str | None = Field(None, description="生成摘要的AI模型版本")
    parent_case_id: int | None = Field(None, description="父用例ID")
    target_device: str | None = Field(None, max_length=20, description="目标设备类型")
    migration_source_id: int | None = Field(None, description="迁移来源用例ID")
    migration_type: str | None = Field(None, max_length=20, description="迁移类型")
    migration_batch_id: str | None = Field(None, max_length=50, description="迁移批次ID")


class TestCaseListRequest(BaseModel):
    __test__ = False
    project_id: int = Field(..., description="项目ID")
    module: str | None = Field(None, description="模块名称")
    priority: int | None = Field(None, ge=1, le=3, description="优先级")
    case_type: str | None = Field(None, description="用例类型")
    generate_status: int | None = Field(None, ge=0, le=2, description="生成状态")
    lifecycle_status: str | None = Field(None, pattern=TEST_CASE_LIFECYCLE_STATUS_PATTERN, description="生命周期状态")
    target_device: str | None = Field(None, description="按目标设备类型筛选")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")


class TestCaseListResponse(BaseModel):
    __test__ = False
    total: int
    items: list[TestCaseResponse]
    page: int
    page_size: int
    stats: dict[str, int] | None = None


class TestCaseDeleteRequest(BaseModel):
    __test__ = False
    project_id: int = Field(..., description="项目ID")
