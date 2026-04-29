"""
测试结果模块 Schema - 测试执行结果的查询与创建模型

本模块定义了测试执行结果的数据契约，包括：

- TestResultResponse: 执行结果响应模型（完整信息）
- TestResultListResponse: 执行结果列表响应
- TestResultCreate: 创建执行结果请求模型

与Model的对应关系：
- TestResult系列 -> app.models.test_result.TestResult
- exec_status -> TestResult.exec_status (整数枚举：0未执行/1成功/2失败/3阻塞)
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TestResultResponse(BaseModel):
    """
    执行结果响应模型

    业务用途：API返回单条用例执行结果时使用
    对应API：GET /api/v1/test-results/{result_id}
    与Model映射：完整映射 TestResult Model 的所有业务字段
    """
    id: int  # 结果主键ID，与TestResult.id对应
    task_id: int  # 所属任务ID，与TestResult.task_id对应
    project_id: int  # 所属项目ID，与TestResult.project_id对应
    case_id: int  # 关联用例ID，与TestResult.case_id对应
    case_no: str  # 用例编号，与TestResult.case_no对应
    exec_status: int  # 执行状态：0未执行/1成功/2失败/3阻塞，与TestResult.exec_status对应
    exec_time: datetime  # 执行时间，与TestResult.exec_time对应
    exec_log: Optional[str] = None  # 可选，单条用例执行日志
    error_msg: Optional[str] = None  # 可选，失败时的错误信息
    screenshot_url: Optional[str] = None  # 可选，失败截图存储路径
    create_time: datetime  # 创建时间
    update_time: datetime  # 更新时间

    class Config:
        # 启用ORM模式，支持从TestResult Model直接读取属性
        from_attributes = True


class TestResultListResponse(BaseModel):
    """
    执行结果列表响应模型

    业务用途：返回执行结果列表查询结果
    对应API：GET /api/v1/test-results/ 的响应
    """
    total: int  # 符合条件的结果总数
    items: list[TestResultResponse]  # 当前页的结果列表


class TestResultCreate(BaseModel):
    """
    创建执行结果请求模型

    业务用途：执行引擎写入单条用例的执行结果
    验证规则：task_id/project_id/case_id/case_no/exec_status必填
    对应API：POST /api/v1/test-results/
    与Model映射：映射 TestResult Model 的 task_id/project_id/case_id/case_no/exec_status等字段
    """
    task_id: int = Field(..., description="任务ID")  # 必填，关联的测试任务
    project_id: int = Field(..., description="项目ID")  # 必填，所属项目
    case_id: int = Field(..., description="用例ID")  # 必填，关联的测试用例
    case_no: str = Field(..., description="用例编号")  # 必填，用例编号，便于快速定位
    exec_status: int = Field(..., description="执行状态")  # 必填，0未执行/1成功/2失败/3阻塞
    exec_log: Optional[str] = Field(None, description="执行日志")  # 可选，详细执行日志
    error_msg: Optional[str] = Field(None, description="错误信息")  # 可选，失败时的错误描述
    screenshot_url: Optional[str] = Field(None, description="截图路径")  # 可选，失败截图URL
