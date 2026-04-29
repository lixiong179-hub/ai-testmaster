"""UI上传Mixin - 处理UI原型文件的上传与预处理。
"""
import os
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
from loguru import logger
from app.crud import ui_prototype as ui_prototype_crud


class UISpecUploadMixin:
    SUPPORTED_IMAGE_TYPES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}

    def _is_image_file(self, filename: str) -> bool:
        ext = os.path.splitext(filename.lower())[1]
        return ext in self.SUPPORTED_IMAGE_TYPES

    def _extract_zip(self, zip_path: str, extract_to: str) -> List[str]:
        import zipfile
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
            logger.error(f"上传并创建屏幕失败: {str(e)}")
            return screen_ids, f"上传失败: {str(e)}"
