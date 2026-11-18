"""Pipeline 权限校验工具（已全部归口，本模块仅做 re-export）

## 沿革

- **R0-3（2026-09-18）**：项目级校验（project × sync/async）归口
  `app/api/v1/endpoints/access_deps.py`，本模块改为 re-export。
- **O-4（2026-11-11）**：迭代级校验（iteration × sync/async）一并归口
  `access_deps`。至此本模块**不再持有任何实现**，三份历史拷贝
  （`pipeline_deps` 的 sync + async、`pipeline_artifacts_helpers` 的 async）
  全部删除；其中 `verify_iteration_access_async` 此前为 0 调用点的死代码。

## 为什么保留本模块

仅为了让既有调用方的 import 路径保持不变（无需改动端点代码）：

    - 项目级：bug.py / pipeline.py / pipeline_precheck.py / mcp_server.py
    - 迭代级：pipeline.py / pipeline_resume.py

**新代码请直接从 `app.api.v1.endpoints.access_deps` 导入**，不要依赖本转发层。
"""

from app.api.v1.endpoints.access_deps import (
    verify_iteration_access,
    verify_iteration_access_async,
    verify_project_access,
    verify_project_access_async,
)

__all__ = [
    "verify_project_access",
    "verify_project_access_async",
    "verify_iteration_access",
    "verify_iteration_access_async",
]
