"""测试用例AI生成 - 请求/响应模型模块

本模块定义AI生成测试用例的全部Pydantic请求和响应模型，供生成端点和流式端点复用。

模型概览:
    - AIGenerateRequest: AI基础生成请求
    - AIGenerateEnhancedRequest: AI增强模式生成请求
    - GenerateContextRequest: 获取AI生成上下文请求
    - SingleGenerateRequest: 基于单个测试点生成请求
    - BatchGenerateRequest: AI批量生成请求
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.test_case import FlowSortDataSchema

MAX_FLOW_NODES = 100
MAX_FLOW_EDGES = 200


class AIGenerateRequest(BaseModel):
    """AI基础生成请求。"""
    project_id: int
    description: str

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("描述不能为空且至少需要10个字符")
        if len(v) > 10000:
            raise ValueError(f"描述过长({len(v)}字符)，最大允许10000字符")
        return v.strip()


class AIGenerateEnhancedRequest(BaseModel):
    """AI增强模式生成请求。"""
    project_id: int
    description: str
    case_type: Optional[str] = None
    exec_mode: str = "all"
    priority: int = 2
    enhanced_mode: bool = True
    context: Optional[dict] = None
    ui_screen_ids: Optional[List[int]] = None
    mode: Literal["linear", "graph"] = Field(
        default="linear", description="排序模式：linear=线性/graph=流程图"
    )
    flow_sort_data: Optional[FlowSortDataSchema] = Field(
        None, description="流程图排序数据（graph模式必填）"
    )

    @field_validator("case_type")
    @classmethod
    def validate_case_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        valid_types = (
            "ui_automation", "manual", "api_automation", "performance",
            "security", "functional", "api_auto", "UI", "API",
        )
        if v not in valid_types:
            raise ValueError(f"不支持的用例类型: {v}")
        from app.core.constants import TestCaseType
        return TestCaseType.from_legacy(v).value

    @field_validator("exec_mode")
    @classmethod
    def validate_exec_mode(cls, v: str) -> str:
        valid_modes = ("all", "ui_auto", "manual")
        if v not in valid_modes:
            raise ValueError(f"不支持的执行模式: {v}")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if len(v.strip()) < 5:
            raise ValueError("描述不能为空且至少需要5个字符")
        if len(v) > 10000:
            raise ValueError(f"描述过长({len(v)}字符)，最大允许10000字符")
        return v.strip()

    @field_validator("flow_sort_data")
    @classmethod
    def validate_flow_sort_data_size(
        cls, v: Optional[FlowSortDataSchema]
    ) -> Optional[FlowSortDataSchema]:
        if v is None:
            return v
        if len(v.nodes) > MAX_FLOW_NODES:
            raise ValueError(f"nodes数量不能超过{MAX_FLOW_NODES}")
        if len(v.edges) > MAX_FLOW_EDGES:
            raise ValueError(f"edges数量不能超过{MAX_FLOW_EDGES}")
        return v


class GenerateContextRequest(BaseModel):
    """获取AI生成上下文请求。"""
    project_id: int
    requirement_file_ids: Optional[List[int]] = None
    ui_file_ids: Optional[List[int]] = None
    ui_screen_ids: Optional[List[int]] = None
    test_point_ids: Optional[List[int]] = None
    history_case_ids: Optional[List[int]] = None
    force_refresh: bool = False
    test_point_page: int = 1
    test_point_page_size: int = 100

    @field_validator("requirement_file_ids", "ui_file_ids", "ui_screen_ids", "test_point_ids")
    @classmethod
    def ensure_list(cls, v: List[int] | None) -> List[int]:
        return v if v is not None else []

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("项目ID必须大于0")
        return v


class SingleGenerateRequest(BaseModel):
    """基于单个测试点生成请求。"""
    project_id: int
    test_point_id: int
    requirement_file_ids: Optional[List[int]] = None
    ui_file_ids: Optional[List[int]] = None
    ui_screen_ids: Optional[List[int]] = None
    force_refresh: bool = False
    case_type: Optional[str] = None

    @field_validator("requirement_file_ids", "ui_file_ids", "ui_screen_ids")
    @classmethod
    def ensure_list(cls, v: List[int] | None) -> List[int]:
        return v if v is not None else []

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("项目ID必须大于0")
        return v

    @field_validator("test_point_id")
    @classmethod
    def validate_test_point_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("测试点ID必须大于0")
        return v


class BatchGenerateRequest(BaseModel):
    """AI批量生成请求。"""
    project_id: int
    test_point_ids: Optional[List[int]] = None
    requirement_file_ids: Optional[List[int]] = None
    ui_file_ids: Optional[List[int]] = None
    ui_screen_ids: Optional[List[int]] = None
    force_refresh: bool = False
    test_point_page: int = 1
    test_point_page_size: int = 100
    case_type: Optional[str] = None

    @field_validator("test_point_ids", "requirement_file_ids", "ui_file_ids", "ui_screen_ids")
    @classmethod
    def ensure_list(cls, v: List[int] | None) -> List[int]:
        return v if v is not None else []

    @field_validator("test_point_ids", "requirement_file_ids", "ui_file_ids", "ui_screen_ids")
    @classmethod
    def validate_list_size(cls, v: List[int] | None) -> List[int] | None:
        if v is not None and len(v) > 200:
            raise ValueError(f"列表长度不能超过200，当前: {len(v)}")
        return v

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("项目ID必须大于0")
        return v

    @field_validator("test_point_page")
    @classmethod
    def validate_page(cls, v: int) -> int:
        if v < 1:
            raise ValueError("页码必须大于等于1")
        return v

    @field_validator("test_point_page_size")
    @classmethod
    def validate_page_size(cls, v: int) -> int:
        if v < 1 or v > 500:
            raise ValueError("每页数量必须在1-500之间")
        return v
