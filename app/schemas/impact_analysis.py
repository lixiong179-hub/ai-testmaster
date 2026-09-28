"""TIA（Test Impact Analysis）Pydantic Schema 定义。

包含 TIA 调度计划、覆盖率映射、配置查询响应的请求/响应模型，
供 TIA 端点与 service 层使用。

响应信封统一使用 app.schemas.common.ApiResponse[T] 泛型封装，例如：
    - ApiResponse[SchedulePlanResponse]     调度计划
    - ApiResponse[CoverageStatsResponse]    覆盖率统计
    - ApiResponse[CoverageIngestResponse]   覆盖率写入结果
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SchedulePlanResponse(BaseModel):
    """TIA 调度计划响应模型，对应 ImpactSchedulePlan。"""

    test_case_ids: List[int] = Field(default_factory=list, description="待执行测试用例 ID 列表")
    is_full_run: bool = Field(..., description="是否全量执行（True 表示降级全量）")
    fallback_reason: str = Field("", description="降级原因（is_full_run=True 时填写）")
    reduction_ratio: float = Field(0.0, description="用例缩减比例（0.0-1.0）")
    estimated_saved_seconds: float = Field(0.0, description="预估节省时间（秒）")
    is_effective: bool = Field(..., description="调度计划是否有效（非全量且缩减比例≥10%）")
    tia_enabled: bool = Field(..., description="TIA 全局开关状态")
    total_test_count: int = Field(0, description="全量用例总数（请求时传入）")


class CoverageMapItem(BaseModel):
    """覆盖率映射条目响应模型，对应 TestCoverageMap 表。"""

    id: int
    project_id: int
    test_case_id: int
    file_path: str
    line_start: int
    line_end: int
    test_name: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CoverageListResponse(BaseModel):
    """覆盖率映射分页列表响应。"""

    items: List[CoverageMapItem]
    total: int
    page: int
    page_size: int


class CoverageStatsResponse(BaseModel):
    """项目级覆盖率统计响应。"""

    project_id: int
    total_mappings: int = Field(0, description="覆盖率映射总条目数")
    unique_files: int = Field(0, description="覆盖的唯一代码文件数")
    unique_test_cases: int = Field(0, description="有覆盖率映射的测试用例数")
    tia_enabled: bool = Field(..., description="TIA 全局开关状态")


class CoverageIngestRequest(BaseModel):
    """覆盖率写入请求：上传 coverage.json 文件路径或直接传 JSON 内容。

    二选一：json_path（服务端可访问路径）或 json_content（coverage.py 字典）。
    """

    test_case_id: int = Field(..., gt=0, description="测试用例 ID")
    test_name: str = Field("", description="测试函数名（调试用）")
    json_path: Optional[str] = Field(None, description="coverage.json 文件路径（服务端可访问）")
    json_content: Optional[dict] = Field(None, description="coverage.py JSON 内容（直接传入）")


class CoverageIngestResponse(BaseModel):
    """覆盖率写入响应。"""

    test_case_id: int
    rows_written: int = Field(0, description="实际写入/更新的映射行数")
    message: str = ""


class SchedulePlanRequest(BaseModel):
    """生成 TIA 调度计划的请求。"""

    total_test_count: int = Field(0, ge=0, description="全量测试用例总数")
    base_ref: Optional[str] = Field(None, description="git diff 基准版本（默认 HEAD~1）")
    target_ref: Optional[str] = Field(None, description="git diff 目标版本（默认 HEAD）")
    avg_test_duration_seconds: Optional[float] = Field(
        None, ge=0.0, description="单次测试用例平均执行时长（秒）"
    )


__all__ = [
    "SchedulePlanResponse",
    "CoverageMapItem",
    "CoverageListResponse",
    "CoverageStatsResponse",
    "CoverageIngestRequest",
    "CoverageIngestResponse",
    "SchedulePlanRequest",
]
