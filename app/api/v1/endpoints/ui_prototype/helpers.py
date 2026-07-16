"""
UI原型辅助工具模块

本模块提供UI原型管理子包的共享工具函数，包括上传目录管理和响应数据构建。

函数概览:
    - _ensure_upload_dir: 确保上传目录存在，不存在则创建
    - _validate_image_file: 验证图片文件是否有效
    - _sanitize_filename_component: 清理文件名组成部分，防止路径遍历
    - _build_screen_response: 将页面ORM对象转换为响应Schema

常量:
    - UPLOAD_DIR: 原型文件上传目录路径，从配置中读取
"""
import os
import re
from typing import Any

import cv2
import numpy as np
from app.core.config import settings

UPLOAD_DIR = settings.UI_PROTOTYPE_UPLOAD_DIR

MIN_IMAGE_SIZE = 1024

# 文件名组成部分安全字符白名单：字母、数字、中文、连字符、下划线、点
# 其余字符（含路径分隔符 / \ .. 等）统一替换为下划线，杜绝路径遍历
_FILENAME_SAFE_PATTERN = re.compile(r'[^\w\u4e00-\u9fa5\-\.]')


def _ensure_upload_dir() -> None:
    """确保上传目录存在，若不存在则递归创建"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def _sanitize_filename_component(component: str) -> str:
    """清理文件名组成部分，防止路径遍历攻击。

    将所有非安全字符（含路径分隔符 / \\、点号序列 .. 等）替换为下划线，
    确保用户输入无法逃逸出目标目录。

    Args:
        component: 用户提供的文件名组成部分（如 prototype_name）

    Returns:
        仅包含安全字符的字符串
    """
    if not component:
        return "unnamed"
    sanitized = _FILENAME_SAFE_PATTERN.sub('_', component)
    # 剥离可能的残留路径分隔符（防御性兜底）
    sanitized = sanitized.replace('/', '_').replace('\\', '_')
    # 防止 ".." 序列残留
    while '..' in sanitized:
        sanitized = sanitized.replace('..', '_')
    return sanitized or "unnamed"


def _validate_image_file(filepath: str) -> tuple[bool, str]:
    """
    验证图片文件是否有效
    
    检查项：
    1. 文件是否存在
    2. 文件大小是否合理（至少1KB）
    3. 能否成功解码为图片
    
    Args:
        filepath: 图片文件路径
    
    Returns:
        (是否有效, 错误信息)
    """
    if not os.path.exists(filepath):
        return False, "文件不存在"
    
    file_size = os.path.getsize(filepath)
    if file_size < MIN_IMAGE_SIZE:
        return False, f"文件太小（{file_size} bytes），可能是损坏的文件"
    
    try:
        with open(filepath, "rb") as f:
            image_bytes = f.read()
        
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return False, "图片解码失败，文件格式可能已损坏"
        
        if img.shape[0] < 10 or img.shape[1] < 10:
            return False, f"图片尺寸过小（{img.shape[1]}x{img.shape[0]}），无法进行OCR识别"
        
        return True, ""
    except Exception as e:
        return False, f"图片验证异常: {str(e)}"


def _isoformat_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _build_screen_response(screen) -> dict[str, Any]:
    """
    构建页面响应数据

    将页面ORM对象转换为UIScreenResponse Schema，包含解析状态中文映射。

    Args:
        screen: 页面ORM对象

    Returns:
        dict: 页面响应数据，字段与当前 UIPrototypeScreen 模型和前端 UIScreen 类型对齐。
    """
    # 解析状态中文映射
    parse_status_map = {
        "pending": "待解析",
        "running": "解析中",
        "completed": "已完成",
        "failed": "解析失败",
    }
    parse_status = screen.parse_status or "pending"
    return {
        "id": screen.id,
        "project_id": screen.project_id,
        "prototype_project_id": screen.prototype_project_id,
        "prototype_name": screen.prototype_name,
        "screen_name": screen.screen_name,
        "screen_order": screen.screen_order or 0,
        "original_file_path": screen.original_file_path,
        "original_file_name": screen.original_file_name,
        "file_type": screen.file_type,
        "file_size": screen.file_size,
        "parse_status": parse_status,
        "parse_status_text": parse_status_map.get(parse_status, parse_status),
        "parse_model": screen.parse_model,
        "parse_error": screen.parse_error,
        "summary": screen.summary,
        "element_count": screen.element_count or 0,
        "button_count": screen.button_count or 0,
        "input_count": screen.input_count or 0,
        "is_entry_point": bool(screen.is_entry_point),
        "is_end_point": bool(screen.is_end_point),
        "review_status": screen.review_status or "pending",
        "ui_spec": screen.ui_spec,
        "layout_checks": screen.layout_checks or [],
        "navigation_flow": screen.navigation_flow,
        "create_time": _isoformat_or_none(screen.create_time),
        "update_time": _isoformat_or_none(screen.update_time),
    }
