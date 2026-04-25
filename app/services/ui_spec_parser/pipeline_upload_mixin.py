"""UI Spec Parse Pipeline Upload Mixin - 上传处理与ZIP解压逻辑。

本模块提供UI原型图批量解析管道中的文件上传处理逻辑，包括
单张/批量图片上传、ZIP包自动解压、屏幕记录创建等。
作为PipelineUploadMixin被UISpecParsePipelineMixin组合使用。

核心类:
    - PipelineUploadMixin: 上传处理Mixin

设计模式:
    作为Mixin模块，通过多继承组合到UISpecParsePipelineMixin中，提供:
    - upload_and_create_screens: 上传文件并创建屏幕记录
    - _extract_zip: 解压ZIP文件
    - _is_image_file: 检查图片文件类型
    - _get_file_size: 获取文件大小

依赖关系:
    - app.crud.ui_prototype: UI原型CRUD操作
    - app.core.config: 配置管理
"""
import zipfile
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.crud import ui_prototype as ui_prototype_crud
from app.core.config import settings
from loguru import logger


class PipelineUploadMixin:
    """上传处理Mixin - 文件上传、ZIP解压与屏幕记录创建。

    职责:
        - 初始化解析管道参数（db, project_id, user_id, upload_dir, parse_mode）
        - 单张/批量图片上传并创建屏幕记录
        - ZIP包自动解压并创建屏幕记录
        - 文件类型检查和大小获取

    设计意图:
        将上传处理逻辑从核心解析管道中抽离，便于:
        1. 独立修改上传逻辑不影响解析流程
        2. 支持不同的上传策略（单文件/批量/ZIP）
        3. 统一管理文件类型和大小校验

    使用场景:
        被UISpecParsePipelineMixin通过多继承组合，
        对外提供upload_and_create_screens接口。
    """

    SUPPORTED_IMAGE_TYPES = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

    def __init__(
        self,
        db,
        project_id: int,
        user_id: int,
        upload_dir: Optional[str] = None,
        parse_mode: Optional[str] = None
    ) -> None:
        """初始化解析管道

        Args:
            db: 数据库会话
            project_id: 项目ID
            user_id: 用户ID
            upload_dir: 上传目录路径
            parse_mode: 解析模式
        """
        self.db = db
        self.project_id = project_id
        self.user_id = user_id
        self.upload_dir = upload_dir or settings.UI_PROTOTYPE_UPLOAD_DIR
        self.parse_mode = parse_mode or getattr(settings, 'UI_PARSER_MODE', 'text')

    def _is_image_file(self, filename: str) -> bool:
        """检查是否为支持的图片文件"""
        ext = os.path.splitext(filename.lower())[1]
        return ext in self.SUPPORTED_IMAGE_TYPES

    def _extract_zip(self, zip_path: str, extract_to: str) -> List[str]:
        """解压ZIP文件，返回图片文件路径列表"""
        image_files = []
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
                for root, dirs, files in os.walk(extract_to):
                    for file in files:
                        if self._is_image_file(file):
                            image_files.append(os.path.join(root, file))
            logger.info(f"ZIP解压完成，共找到{len(image_files)}张图片")
        except Exception as e:
            logger.error(f"ZIP解压失败: {str(e)}")
        return image_files

    def _get_file_size(self, file_path: str) -> int:
        """获取文件大小（KB）"""
        try:
            return os.path.getsize(file_path) // 1024
        except Exception:
            return 0

    async def upload_and_create_screens(
        self,
        files: List[Dict[str, Any]],
        prototype_name: str,
        prototype_project_id: Optional[int] = None,
        is_zip: bool = False
    ) -> Tuple[List[int], str]:
        """上传文件并创建屏幕记录

        Args:
            files: 文件列表，每项包含 path/name/size
            prototype_name: 原型名称
            prototype_project_id: 原型项目ID
            is_zip: 是否为ZIP包

        Returns:
            (创建的屏幕ID列表, 状态消息)
        """
        screen_ids = []

        try:
            if is_zip and files:
                zip_path = files[0]['path']
                extract_dir = os.path.join(
                    self.upload_dir,
                    f"{self.project_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                )
                os.makedirs(extract_dir, exist_ok=True)

                image_files = self._extract_zip(zip_path, extract_dir)

                if not image_files:
                    return [], "ZIP包中未找到支持的图片文件"

                image_files.sort()

                screens_data = []
                for i, img_path in enumerate(image_files):
                    screens_data.append({
                        'prototype_name': prototype_name,
                        'screen_name': os.path.splitext(os.path.basename(img_path))[0],
                        'file_path': img_path,
                        'file_name': os.path.basename(img_path),
                        'file_type': os.path.splitext(img_path)[1][1:],
                        'file_size': self._get_file_size(img_path),
                        'screen_order': i
                    })

                screens = ui_prototype_crud.batch_create_ui_screens(
                    db=self.db,
                    project_id=self.project_id,
                    screens_data=screens_data,
                    created_by=self.user_id,
                    prototype_project_id=prototype_project_id
                )
                screen_ids = [s.id for s in screens]

            else:
                for i, file_info in enumerate(files):
                    screen = ui_prototype_crud.create_ui_screen(
                        db=self.db,
                        project_id=self.project_id,
                        prototype_name=prototype_name,
                        screen_name=file_info.get('name', f'屏幕{i+1}').rsplit('.', 1)[0],
                        original_file_path=file_info['path'],
                        original_file_name=file_info['name'],
                        file_type=file_info.get('name', 'png').rsplit('.', 1)[-1],
                        file_size=file_info.get('size', 0) // 1024,
                        screen_order=i,
                        created_by=self.user_id,
                        prototype_project_id=prototype_project_id
                    )
                    screen_ids.append(screen.id)

            if prototype_project_id:
                ui_prototype_crud.update_prototype_project_stats(self.db, prototype_project_id)

            return screen_ids, f"成功创建{len(screen_ids)}个屏幕记录"

        except Exception as e:
            logger.error(f"上传并创建屏幕失败: {e}")
            return screen_ids, "上传失败"
