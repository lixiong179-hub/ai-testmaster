"""测试任务端点辅助模块

本模块包含测试任务端点使用的请求模型，从 test_task.py 拆出以控制单文件行数。

内容:
    - 请求模型定义（CreateTaskRequest / TaskStartConfig）

注（2026-09-18，R0-3 归属校验归一）：
    原位于本模块的 4 个项目/任务归属校验函数（_verify_project_access、
    _verify_task_access 及其 async 版本）已删除——它们与
    test_task_exec.py、pipeline_deps.py 中的实现逐字重复，且 sync 版本
    全库无调用点。
    统一实现源：``app/api/v1/endpoints/access_deps.py``：
        - verify_project_access[_async] → 项目 ID 来自 body/query 时内联调用
        - require_task_access           → 路径参数为 task_id 时用依赖注入
"""
from pydantic import BaseModel, Field
from typing import List, Optional


# 创建任务请求模型
class CreateTaskRequest(BaseModel):
    project_id: int
    task_name: str
    description: Optional[str] = None
    case_ids: List[int] = Field(default_factory=list)


class TaskStartConfig(BaseModel):
    """任务启动配置模型"""
    execution_mode: Optional[str] = Field("smart", description="执行模式")
    mobile_device_id: Optional[str] = Field(None, description="移动设备ID")
