"""
UI原型管理模块（聚合入口）

本模块为UI原型功能的聚合入口，将UI原型相关的子模块统一注册到同一路由前缀下。
实际端点定义在ui_prototype子包中。

路由前缀: /ui-prototype
标签: UI原型管理

子模块概览:
    - ui_prototype.project_endpoints: 项目级原型管理
    - ui_prototype.screen_endpoints: 页面级原型管理
    - ui_prototype.parse_endpoints: 原型解析端点

所有端点均需要Bearer令牌认证。
"""

from app.api.v1.endpoints.ui_prototype import (
    router, 
    UPLOAD_DIR, 
    _ensure_upload_dir, 
    _build_screen_response
)

__all__ = [
    'router',
    'UPLOAD_DIR',
    '_ensure_upload_dir',
    '_build_screen_response',
]