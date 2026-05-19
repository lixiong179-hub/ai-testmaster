from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class TechnicalLocatorInfo(BaseModel):
    css_selector: Optional[str] = Field(None, description="CSS选择器")
    xpath: Optional[str] = Field(None, description="XPath定位器")
    element_type: Optional[str] = Field(None, description="元素类型")
    ai_coordinate: Optional[Dict[str, float]] = Field(None, description="AI识别坐标")
    confidence: Optional[float] = Field(None, description="置信度")
    locator_type: Optional[str] = Field(None, description="定位类型: css/xpath/id/name/ai")
    locator_value: Optional[str] = Field(None, description="定位值")


class TechnicalStepView(BaseModel):
    step_number: int = Field(..., description="步骤编号")
    action: str = Field(..., description="操作描述")
    expected_result: str = Field(..., description="预期结果")
    has_locator: bool = Field(..., description="是否有定位信息")
    locator_status: str = Field(..., description="定位状态: pending/recorded/failed")
    locator: Optional[TechnicalLocatorInfo] = Field(None, description="定位详情")
    test_data: Optional[Dict[str, Any]] = Field(None, description="测试数据")


class ExecutionHistoryItem(BaseModel):
    execution_id: int = Field(..., description="执行ID")
    execution_time: datetime = Field(..., description="执行时间")
    status: str = Field(..., description="执行状态: success/failed/running")
    duration: Optional[float] = Field(None, description="执行时长(秒)")
    error_message: Optional[str] = Field(None, description="错误信息")
    screenshot_url: Optional[str] = Field(None, description="截图URL")


class TechnicalTestCaseView(BaseModel):
    case_id: int = Field(..., description="用例ID")
    case_no: str = Field(..., description="用例编号")
    title: str = Field(..., description="用例标题")
    module: Optional[str] = Field(None, description="所属模块")
    precondition: Optional[str] = Field(None, description="前置条件")
    expected_result: Optional[str] = Field(None, description="整体预期结果")
    priority: Optional[int] = Field(None, description="优先级")
    case_type: Optional[str] = Field(None, description="用例类型")

    steps: List[TechnicalStepView] = Field(..., description="步骤列表")
    precondition_steps: List["PreconditionStepResponse"] = Field([], description="前置条件步骤列表")
    locator_coverage: float = Field(..., description="定位覆盖率")

    execution_history: List[ExecutionHistoryItem] = Field([], description="执行历史")

    class Config:
        from_attributes = True


from app.schemas.test_case._precondition import PreconditionStepResponse  # noqa: E402

TechnicalTestCaseView.model_rebuild()
