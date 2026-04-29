"""
测试任务模块 Schema - 测试任务创建/执行/管理的请求与响应模型

本模块定义了测试任务全生命周期的数据契约，包括：

测试任务Schema分层：
- TestTaskCreate: 创建测试任务请求（指定用例列表）
- TestTaskUpdate: 更新测试任务请求（状态/进度/计数）
- TestTaskResponse: 测试任务响应模型（完整信息）
- TestTaskListResponse: 测试任务列表分页响应
- TestTaskCreateResponse: 创建任务成功后的精简响应

与Model的对应关系：
- TestTask系列 -> app.models.test_task.TestTask
- case_ids -> TestTask.case_ids (JSON字段)
- status -> TestTask.status (整数枚举：0等待/1执行中/2完成/3失败/4停止)
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TestTaskCreate(BaseModel):
    """
    创建测试任务请求模型

    业务用途：创建新的测试执行任务，指定待执行的用例列表
    验证规则：task_name/project_id/case_ids均必填
    对应API：POST /api/v1/test-tasks/
    与Model映射：映射 TestTask Model 的 task_name/project_id/case_ids 字段
    """
    task_name: str = Field(..., description="任务名称")  # 必填，任务标识名称，如"登录模块回归测试"
    project_id: int = Field(..., description="项目ID")  # 必填，任务所属项目，实现多项目隔离
    case_ids: List[int] = Field(..., description="待执行用例ID列表")  # 必填，需执行的测试用例ID列表，存储为JSON


class TestTaskUpdate(BaseModel):
    """
    更新测试任务请求模型

    业务用途：更新任务执行状态、进度和计数，通常由执行引擎调用
    验证规则：所有字段可选，进度0-100，计数非负
    对应API：PUT/PATCH /api/v1/test-tasks/{task_id}
    与Model映射：字段对应 TestTask Model 的 task_name/status/progress/success_count/fail_count
    """
    task_name: Optional[str] = Field(None, description="任务名称")  # 可选，更新任务名称
    status: Optional[int] = Field(None, description="任务状态")  # 可选，0=等待/1执行中/2完成/3失败/4停止
    progress: Optional[int] = Field(None, ge=0, le=100, description="执行进度")  # 可选，0-100百分比
    success_count: Optional[int] = Field(None, ge=0, description="成功用例数")  # 可选，执行成功的用例计数
    fail_count: Optional[int] = Field(None, ge=0, description="失败用例数")  # 可选，执行失败的用例计数


class TestTaskResponse(BaseModel):
    """
    测试任务响应模型

    业务用途：API返回测试任务完整信息时使用
    对应API：GET /api/v1/test-tasks/{task_id}
    与Model映射：完整映射 TestTask Model 的所有业务字段
    """
    id: int  # 任务主键ID，与TestTask.id对应
    task_name: str  # 任务名称，与TestTask.task_name对应
    project_id: int  # 所属项目ID，与TestTask.project_id对应
    case_ids: List[int]  # 待执行用例ID列表，与TestTask.case_ids(JSON)对应
    executor_id: int  # 执行人ID，与TestTask.executor_id对应
    status: int  # 任务状态：0等待/1执行中/2完成/3失败/4停止，与TestTask.status对应
    start_time: Optional[datetime] = None  # 开始执行时间，可能为空（未开始）
    end_time: Optional[datetime] = None  # 结束执行时间，可能为空（未完成）
    success_count: int  # 成功用例数，与TestTask.success_count对应
    fail_count: int  # 失败用例数，与TestTask.fail_count对应
    total_count: int  # 总用例数，与TestTask.total_count对应
    progress: int  # 执行进度0-100，与TestTask.progress对应
    create_time: datetime  # 创建时间，与TestTask.create_time对应
    update_time: datetime  # 更新时间，与TestTask.update_time对应

    class Config:
        # 启用ORM模式，支持从TestTask Model直接读取属性
        from_attributes = True


class TestTaskListResponse(BaseModel):
    """
    测试任务列表分页响应模型

    业务用途：返回分页查询结果
    对应API：GET /api/v1/test-tasks/ 的响应
    """
    total: int  # 符合条件的任务总数
    items: List[TestTaskResponse]  # 当前页的任务列表
    page: int  # 当前页码
    page_size: int  # 每页数量


class TestTaskCreateResponse(BaseModel):
    """
    创建测试任务响应模型

    业务用途：创建任务成功后返回精简信息，避免返回完整数据
    对应API：POST /api/v1/test-tasks/ 的成功响应
    """
    task_id: int  # 新创建的任务ID
    task_name: str  # 任务名称
    project_id: int  # 所属项目ID
    total_count: int  # 待执行用例总数
    create_time: datetime  # 创建时间
