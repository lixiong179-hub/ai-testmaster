from pydantic import BaseModel, Field

from app.schemas.test_case._technical import TechnicalLocatorInfo


class PreconditionStepCreate(BaseModel):
    step_number: int = Field(..., description="步骤序号")
    action: str = Field(..., description="操作步骤")
    expected_result: str = Field("", description="预期结果")
    action_type: str | None = Field(None, description="操作类型")
    input_value: str | None = Field(None, description="输入值")
    target_element: str | None = Field(None, description="目标元素描述")


class PreconditionStepUpdate(BaseModel):
    step_number: int | None = Field(None, description="步骤序号")
    action: str | None = Field(None, description="操作步骤")
    expected_result: str | None = Field(None, description="预期结果")
    action_type: str | None = Field(None, description="操作类型")
    input_value: str | None = Field(None, description="输入值")
    target_element: str | None = Field(None, description="目标元素描述")


class PreconditionStepResponse(BaseModel):
    id: int
    test_case_id: int
    step_number: int
    action: str
    expected_result: str
    action_type: str | None = None
    input_value: str | None = None
    target_element: str | None = None
    has_locator: bool
    locator_status: str
    locator: TechnicalLocatorInfo | None = None

    class Config:
        from_attributes = True


class PreconditionStepBatchSave(BaseModel):
    steps: list[PreconditionStepCreate] = Field(..., description="前置条件步骤列表")
