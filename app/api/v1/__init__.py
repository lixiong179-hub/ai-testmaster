"""
API V1版本路由模块

本模块为API V1版本的模块索引入口，列出所有已注册的业务端点模块。
路由实际注册由 app/main.py 统一管理，各模块 router 直接挂载到 FastAPI app。

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
    - /audit-log         - 审计日志

注意:
    - 所有模块均在自身APIRouter中定义了prefix
    - 所有端点均需要Bearer令牌认证（除认证模块的登录/注册/验证码端点外）
"""
from app.api.v1.endpoints import (
    auth, user, test_task, project, file, test_point, test_case,
    requirement_link, ui_prototype, iteration, execution,
    execution_visualization, batch_locator, test_data, case_quality,
    report, visibility, audit_log, pipeline, review_inbox, test_capability,
    websocket
)