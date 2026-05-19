from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.schemas.test_case._technical import TechnicalLocatorInfo


class PreconditionStepCreate(BaseModel):
    step_number: int = Field(..., description="步骤序号")
    action: str = Field(..., description="操作步骤")
    expected_result: str = Field("", description="预期结果")
    action_type: Optional[str] = Field(None, description="操作类型")
    input_value: Optional[str] = Field(None, description="输入值")
    target_element: Optional[str] = Field(None, description="目标元素描述")


class PreconditionStepUpdate(BaseModel):
    step_number: Optional[int] = Field(None, description="步骤序号")
    action: Optional[str] = Field(None, description="操作步骤")
    expected_result: Optional[str] = Field(None, description="预期结果")
    action_type: Optional[str] = Field(None, description="操作类型")
    input_value: Optional[str] = Field(None, description="输入值")
    target_element: Optional[str] = Field(None, description="目标元素描述")


class PreconditionStepResponse(BaseModel):
    id: int
    test_case_id: int
    step_number: int
    action: str
    expected_result: str
    action_type: Optional[str] = None
    input_value: Optional[str] = None
    target_element: Optional[str] = None
    has_locator: bool
    locator_status: str
    locator: Optional[TechnicalLocatorInfo] = None

    class Config:
        from_attributes = True


class PreconditionStepBatchSave(BaseModel):
    steps: List[PreconditionStepCreate] = Field(..., description="前置条件步骤列表")
