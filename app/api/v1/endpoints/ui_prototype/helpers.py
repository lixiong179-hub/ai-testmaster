"""
UI原型辅助工具模块

本模块提供UI原型管理子包的共享工具函数，包括上传目录管理和响应数据构建。

函数概览:
    - _ensure_upload_dir: 确保上传目录存在，不存在则创建
    - _build_screen_response: 将页面ORM对象转换为响应Schema

常量:
    - UPLOAD_DIR: 原型文件上传目录路径，从配置中读取
"""
import os
from app.core.config import settings
from app.schemas.ui_prototype import UIScreenResponse

# 原型文件上传目录，从应用配置中读取，默认为/tmp/ui_prototypes
UPLOAD_DIR = getattr(settings, "UI_PROTOTYPE_UPLOAD_DIR", "/tmp/ui_prototypes")


def _ensure_upload_dir() -> None:
    """确保上传目录存在，若不存在则递归创建"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def _build_screen_response(screen) -> UIScreenResponse:
    """
    构建页面响应数据

    将页面ORM对象转换为UIScreenResponse Schema，包含解析状态中文映射。

    Args:
        screen: 页面ORM对象

    Returns:
        UIScreenResponse: 页面响应Schema对象
    """
    # 解析状态中文映射
    parse_status_map = {
        "pending": "待解析",
        "running": "解析中",
        "completed": "已完成",
        "failed": "解析失败",
    }
    return UIScreenResponse(
        id=screen.id,
        project_id=screen.project_id,
        prototype_project_id=screen.prototype_project_id,
        prototype_name=screen.prototype_name,
        screen_name=screen.screen_name,
        screen_order=screen.screen_order,
        original_file_path=screen.original_file_path,
        original_file_name=screen.original_file_name,
        file_type=screen.file_type,
        file_size=screen.file_size,
        parse_status=screen.parse_status,
        parse_status_text=parse_status_map.get(
            screen.parse_status, screen.parse_status
        ),
        parse_model=screen.parse_model,
        parse_error=screen.parse_error,
        summary=screen.summary,
        element_count=screen.element_count,
        button_count=screen.button_count,
        input_count=screen.input_count,
        is_entry_point=screen.is_entry_point,
        is_end_point=screen.is_end_point,
        review_status=screen.review_status,
        create_time=screen.create_time,
        update_time=screen.update_time,
    )
