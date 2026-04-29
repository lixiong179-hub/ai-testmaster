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
    - /testPoint         - 测试点管理（CRUD/AI生成）
    - /testCase          - 测试用例管理（CRUD/AI生成/工作流/版本）
    - /requirement-link  - 需求链接管理（CRUD/外部同步）
    - /ui-prototype      - UI原型管理（上传/解析/元素标注）
    - /iteration         - 迭代管理

注意:
    - 部分模块在子路由中已定义prefix，此处不再重复添加
    - 所有端点均需要Bearer令牌认证（除认证模块的登录/注册/验证码端点外）
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, test_task, user, project, file, test_point, test_case, requirement_link, ui_prototype, iteration

api_router = APIRouter()

# 认证路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])

# 用户与权限管理路由
api_router.include_router(user.router, prefix="/user", tags=["用户权限管理"])

# 测试任务路由
api_router.include_router(test_task.router, prefix="/test_task", tags=["测试任务"])

# 项目管理路由
api_router.include_router(project.router, tags=["项目管理"])

# 文件管理路由
api_router.include_router(file.router, tags=["文件管理"])

# 测试点路由
api_router.include_router(test_point.router, tags=["测试点管理"])

# 测试用例路由（包含技术视图API）
api_router.include_router(test_case.router, prefix="/testCase", tags=["测试用例管理"])

# 需求链接管理路由
api_router.include_router(requirement_link.router, prefix="/requirement-link", tags=["需求链接管理"])

# UI原型管理路由（摹客UI图视觉解析）
api_router.include_router(ui_prototype.router, tags=["UI原型管理"])

# 迭代管理路由
api_router.include_router(iteration.router, tags=["迭代管理"])
