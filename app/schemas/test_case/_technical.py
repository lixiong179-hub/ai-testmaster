from pydantic import BaseModel, Field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 仅类型检查：运行时由 _precondition 的延迟导入 + model_rebuild 注入（见本模块末尾）
    from app.schemas.test_case._precondition import PreconditionStepResponse
from datetime import datetime


class TechnicalLocatorInfo(BaseModel):
    css_selector: str | None = Field(None, description="CSS选择器")
    xpath: str | None = Field(None, description="XPath定位器")
    element_type: str | None = Field(None, description="元素类型")
    ai_coordinate: dict[str, float] | None = Field(None, description="AI识别坐标")
    confidence: float | None = Field(None, description="置信度")
    locator_type: str | None = Field(None, description="定位类型: css/xpath/id/name/ai")
    locator_value: str | None = Field(None, description="定位值")


class TechnicalStepView(BaseModel):
    step_number: int = Field(..., description="步骤编号")
    action: str = Field(..., description="操作描述")
    expected_result: str = Field(..., description="预期结果")
    has_locator: bool = Field(..., description="是否有定位信息")
    locator_status: str = Field(..., description="定位状态: pending/recorded/failed")
    locator: TechnicalLocatorInfo | None = Field(None, description="定位详情")
    test_data: dict[str, Any] | None = Field(None, description="测试数据")


class ExecutionHistoryItem(BaseModel):
    execution_id: int = Field(..., description="执行ID")
    execution_time: datetime = Field(..., description="执行时间")
    status: str = Field(..., description="执行状态: success/failed/running")
    duration: float | None = Field(None, description="执行时长(秒)")
    error_message: str | None = Field(None, description="错误信息")
    screenshot_url: str | None = Field(None, description="截图URL")


class TechnicalTestCaseView(BaseModel):
    case_id: int = Field(..., description="用例ID")
    case_no: str = Field(..., description="用例编号")
    title: str = Field(..., description="用例标题")
    module: str | None = Field(None, description="所属模块")
    precondition: str | None = Field(None, description="前置条件")
    expected_result: str | None = Field(None, description="整体预期结果")
    priority: int | None = Field(None, description="优先级")
    case_type: str | None = Field(None, description="用例类型")

    steps: list[TechnicalStepView] = Field(..., description="步骤列表")
    precondition_steps: list["PreconditionStepResponse"] = Field([], description="前置条件步骤列表")
    locator_coverage: float = Field(..., description="定位覆盖率")

    execution_history: list[ExecutionHistoryItem] = Field([], description="执行历史")

    class Config:
        from_attributes = True


def _rebuild_technical_view() -> None:
    """R4-7：以函数内导入 + 显式命名空间完成前向引用重建。

    `precondition_steps` 使用字符串前向引用 `"PreconditionStepResponse"`，
    与 `_precondition`（导入本模块的 `TechnicalLocatorInfo`）构成互相依赖。
    把导入放进函数并显式传入 `_types_namespace`，运行时行为不变，
    但消除模块级循环依赖。
    """
    from app.schemas.test_case._precondition import PreconditionStepResponse

    TechnicalTestCaseView.model_rebuild(_types_namespace={"PreconditionStepResponse": PreconditionStepResponse})


_rebuild_technical_view()
