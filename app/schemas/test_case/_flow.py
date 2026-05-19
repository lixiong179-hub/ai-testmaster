from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Literal


class FlowMetaSchema(BaseModel):
    parent_node_id: Optional[str] = Field(None, max_length=50, description="挂靠父节点ID")
    parent_main_node_id: Optional[str] = Field(None, max_length=50, description="兼容旧数据的父节点ID")
    trigger_condition: Optional[str] = Field(None, max_length=500, description="触发条件")
    pre_action: Optional[str] = Field(None, max_length=500, description="前置操作")
    expected_result: Optional[str] = Field(None, max_length=500, description="预期结果")
    bypass_reason: Optional[str] = Field(None, max_length=500, description="旁路原因")
    note: Optional[str] = Field(None, max_length=500, description="备注")


class FlowNodeSchema(BaseModel):
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
    flow_meta: Optional[FlowMetaSchema] = Field(
        None,
        description="流程补充信息，含 pre_action/expected_result/bypass_reason/note"
    )
    image_url: Optional[str] = Field(None, max_length=2000, description="截图URL，用于多模态Prompt")

    @field_validator('screen_name')
    @classmethod
    def screen_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('screen_name不能为纯空白字符')
        return v.strip()


class FlowEdgeSchema(BaseModel):
    source: str = Field(..., min_length=1, description="源节点screen_id的字符串形式")
    target: str = Field(..., min_length=1, description="目标节点screen_id的字符串形式")
    edge_type: Literal['normal', 'branch', 'exception', 'bypass'] = Field(
        ..., description="连线类型：normal=正常/branch=分支/exception=异常/bypass=旁路"
    )
    condition: Optional[str] = Field(None, max_length=500, description="触发条件/异常场景")
    label: str = Field(..., min_length=1, max_length=100, description="连线显示标签")
    trigger_action: Optional[str] = Field(None, max_length=500, description="触发动作描述")
    pre_action: Optional[str] = Field(None, max_length=500, description="前置操作描述")
    note: Optional[str] = Field(None, max_length=500, description="备注信息")

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
    nodes: List[FlowNodeSchema] = Field(..., min_length=1, description="节点列表")
    edges: List[FlowEdgeSchema] = Field(default_factory=list, description="连线列表")
    module_info: Optional[Dict[str, Any]] = Field(None, description="模块基础信息")
