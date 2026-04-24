"""
API V1版本路由模块

本模块为API V1版本的聚合入口，将所有业务模块的路由统一注册到api_router下。
所有V1版本的API端点均通过此模块注册，路径前缀为 /api/v1。

路由注册概览:
    - /auth              - 认证管理（登录/注册/验证码）
    - /user              - 用户权限管理（用户信息/密码修改）
    - /test_task         - 测试任务管理
    - /project           - 项目管理（CRUD/配置/被测对象）
    - /file              - 文件管理（上传/下载/导出）
    - /test-point        - 测试点管理（CRUD/AI生成）
    - /testCase          - 测试用例管理（CRUD/AI生成/工作流/版本）
    - /requirement-link  - 需求链接管理（CRUD/外部同步）
    - /ui-prototype      - UI原型管理（上传/解析/元素标注）
    - /iteration         - 迭代管理
    - /execution         - 测试执行（核心/管理/可视化/回放）
    - /batch-locator     - 批量定位器
    - /test-data         - 测试数据管理
    - /quality           - 用例质量（检查/报告）
    - /report            - 测试报告管理
    - /visibility        - 可见性管理

注意:
    - 所有模块均在自身APIRouter中定义了prefix，此处不再重复添加
    - 所有端点均需要Bearer令牌认证（除认证模块的登录/注册/验证码端点外）
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, user, test_task, project, file, test_point, test_case,
    requirement_link, ui_prototype, iteration, execution,
    execution_visualization, batch_locator, test_data, case_quality,
    report, visibility
)

api_router = APIRouter()

# 认证路由（模块自带prefix=/auth）
api_router.include_router(auth.router, tags=["认证"])

# 用户与权限管理路由（模块自带prefix=/user）
api_router.include_router(user.router, tags=["用户权限管理"])

# 测试任务路由（模块自带prefix=/test_task）
api_router.include_router(test_task.router, tags=["测试任务"])

# 项目管理路由（模块自带prefix=/project）
api_router.include_router(project.router, tags=["项目管理"])

# 文件管理路由（模块自带prefix=/file）
api_router.include_router(file.router, tags=["文件管理"])

# 测试点路由（模块自带prefix=/test-point）
api_router.include_router(test_point.router, tags=["测试点管理"])

# 测试用例路由（模块自带prefix=/testCase）
api_router.include_router(test_case.router, tags=["测试用例管理"])

# 需求链接管理路由（模块自带prefix=/requirement-link）
api_router.include_router(requirement_link.router, tags=["需求链接管理"])

# UI原型管理路由（模块自带prefix=/ui-prototype）
api_router.include_router(ui_prototype.router, tags=["UI原型管理"])

# 迭代管理路由（模块自带prefix=/iteration）
api_router.include_router(iteration.router, tags=["迭代管理"])

# 测试执行路由（模块自带prefix=/execution）
api_router.include_router(execution.router, tags=["测试执行"])

# 执行可视化路由（模块自带prefix=/execution，与execution共享前缀）
api_router.include_router(execution_visualization.router, tags=["测试执行可视化"])

# 批量定位器路由（模块自带prefix=/batch-locator）
api_router.include_router(batch_locator.router, tags=["批量定位器"])

# 测试数据路由（模块自带prefix=/test-data）
api_router.include_router(test_data.router, tags=["测试数据管理"])

# 用例质量路由（模块自带prefix=/quality）
api_router.include_router(case_quality.router, tags=["用例质量"])

# 测试报告路由（模块自带prefix=/report）
api_router.include_router(report.router, tags=["测试报告管理"])

# 可见性管理路由（模块自带prefix=/visibility）
api_router.include_router(visibility.router, tags=["可见性管理"])
