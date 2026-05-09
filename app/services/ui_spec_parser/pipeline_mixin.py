"""UI Spec Parse Pipeline Mixin - UI原型图批量解析管道

提供批量上传、异步解析、进度查询等完整管道
支持：
1. 单张/批量图片上传（继承自PipelineUploadMixin）
2. ZIP包自动解压（继承自PipelineUploadMixin）
3. 异步批量解析
4. 解析进度查询
5. 多图流转合并
6. 与测试用例关联
"""
import asyncio
import shutil
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import base64

from sqlalchemy.orm import Session

from app.crud import ui_prototype as ui_prototype_crud
from app.services.ui_spec_parser import ui_spec_parser, UISpecParser
from app.services.ui_spec_parser.pipeline_upload_mixin import PipelineUploadMixin
from app.utils.unified_vision_model import get_default_vision_model
from app.core.config import settings
from loguru import logger


class UISpecParsePipelineMixin(PipelineUploadMixin):
    """UI原型图批量解析管道Mixin"""

    def __init__(
        self,
        db: Session,
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
        super().__init__(db, project_id, user_id, upload_dir, parse_mode)
        self.parser = UISpecParser(parse_mode=self.parse_mode)

    async def parse_screen(self, screen_id: int) -> Tuple[bool, str]:
        """解析单个屏幕

        Args:
            screen_id: 屏幕ID

        Returns:
            (成功标志, 消息)
        """
        screen = ui_prototype_crud.get_ui_screen_by_id(self.db, screen_id, self.project_id)
        if not screen:
            return False, "屏幕不存在"

        if not screen.original_file_path or not os.path.exists(screen.original_file_path):
            return False, "原始图片文件不存在"

        ui_prototype_crud.update_ui_screen_parse_status(self.db, screen_id, "running")

        try:
            success, ui_spec, error = await self.parser.parse_single_screen(
                image_path=screen.original_file_path,
                screen_name_hint=screen.screen_name
            )

            if success:
                ui_spec['_parse_mode'] = self.parse_mode

                elements = ui_spec.get('elements', [])
                buttons = [e for e in elements if e.get('type') == 'button']

                # 根据解析模式记录对应的模型名称
                if self.parse_mode == settings.PARSE_MODE_TEXT:
                    parse_model = getattr(settings, 'TEXT_MODEL_NAME', '') or settings.DEEPSEEK_MODEL
                else:
                    parse_model = self.parser.vision_model.model_name

                ui_prototype_crud.update_ui_screen_parse_result(
                    db=self.db,
                    screen_id=screen_id,
                    ui_spec=ui_spec,
                    parse_model=parse_model,
                    summary=ui_spec.get('purpose', ''),
                    element_count=len(elements),
                    button_count=len(buttons),
                    input_count=len([e for e in elements if e.get('type') == 'input']),
                    layout_checks=ui_spec.get('layout_constraints', []),
                    navigation_flow=ui_spec.get('flows', {}),
                    is_entry_point=screen.screen_order == 0,
                    is_end_point=len((ui_spec.get('flows') or {}).get('expected_next_screens', [])) == 0
                )
                return True, "解析成功"
            else:
                ui_prototype_crud.update_ui_screen_parse_status(
                    self.db, screen_id, "failed", error
                )
                return False, error

        except Exception as e:
            logger.error(f"解析屏幕失败: {e}")
            ui_prototype_crud.update_ui_screen_parse_status(
                self.db, screen_id, "failed", str(e)
            )
            return False, "解析失败"

    async def batch_parse_screens(
        self,
        screen_ids: List[int],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """批量解析屏幕

        Args:
            screen_ids: 屏幕ID列表
            progress_callback: 进度回调函数

        Returns:
            解析结果统计
        """
        success_count = 0
        failed_count = 0
        results = []

        for i, screen_id in enumerate(screen_ids):
            if progress_callback:
                progress = int((i / len(screen_ids)) * 100)
                progress_callback(progress, f"正在解析第{i+1}/{len(screen_ids)}张...")

            success, msg = await self.parse_screen(screen_id)
            if success:
                success_count += 1
            else:
                failed_count += 1

            results.append({'screen_id': screen_id, 'success': success, 'message': msg})

        if progress_callback:
            progress_callback(100, "解析完成")

        return {
            'total': len(screen_ids),
            'success': success_count,
            'failed': failed_count,
            'results': results,
            'parse_mode': self.parse_mode
        }

    async def parse_prototype_project(
        self,
        prototype_project_id: int,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """解析整个原型项目

        Args:
            prototype_project_id: 原型项目ID
            progress_callback: 进度回调

        Returns:
            解析结果
        """
        screens = ui_prototype_crud.get_ui_screens_by_project(
            db=self.db,
            project_id=self.project_id,
            user_id=self.user_id,
            prototype_project_id=prototype_project_id,
            parse_status="pending"
        )

        screen_ids = [s.id for s in screens]

        if not screen_ids:
            return {'message': '没有待解析的屏幕', 'total': 0}

        result = await self.batch_parse_screens(screen_ids, progress_callback)

        if result['success'] > 0:
            await self.generate_flow(prototype_project_id)

        ui_prototype_crud.update_prototype_project_stats(self.db, prototype_project_id)

        return result

    async def generate_flow(self, prototype_project_id: int) -> Tuple[bool, str]:
        """为原型项目生成页面流转

        Args:
            prototype_project_id: 原型项目ID

        Returns:
            (成功标志, 消息)
        """
        screens = ui_prototype_crud.get_parsed_ui_screens_for_case_generation(
            db=self.db,
            project_id=self.project_id,
            user_id=self.user_id,
            prototype_project_id=prototype_project_id
        )

        if len(screens) < 2:
            return False, "需要至少2个已解析的屏幕才能生成流转"

        screens_data = []
        for screen in screens:
            if screen.ui_spec:
                screens_data.append({
                    'screen_id': screen.id,
                    'screen_name': screen.screen_name,
                    'summary': screen.summary,
                    'navigation': screen.navigation_flow,
                    'elements': screen.ui_spec.get('elements', []) if screen.ui_spec else []
                })

        merged_flow = self.parser.parse_multiple_screen_flows(screens_data)

        if merged_flow:
            ui_prototype_crud.update_prototype_project_merged_flow(
                self.db, prototype_project_id, merged_flow
            )
            return True, "页面流转生成成功"

        return False, "页面流转生成失败"

    def get_parsed_ui_spec_for_case_generation(
        self,
        prototype_project_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取已解析的UI规格，用于生成测试用例

        Args:
            prototype_project_id: 原型项目ID

        Returns:
            ui_spec列表
        """
        screens = ui_prototype_crud.get_parsed_ui_screens_for_case_generation(
            db=self.db,
            project_id=self.project_id,
            user_id=self.user_id,
            prototype_project_id=prototype_project_id,
            approved_only=False
        )

        result = []
        for screen in screens:
            if screen.ui_spec:
                result.append({
                    'screen_id': screen.id,
                    'screen_name': screen.screen_name,
                    'prototype_name': screen.prototype_name,
                    'screen_order': screen.screen_order,
                    'ui_spec': screen.ui_spec,
                    'summary': screen.summary,
                    'layout_checks': screen.layout_checks or [],
                    'navigation_flow': screen.navigation_flow,
                    'element_count': screen.element_count,
                    'button_count': screen.button_count,
                    'is_entry_point': screen.is_entry_point,
                    'is_end_point': screen.is_end_point,
                    'review_status': screen.review_status
                })

        return result


class UISpecParseService:
    """UI解析服务同步包装器"""

    @staticmethod
    def create_pipeline(
        db: Session,
        project_id: int,
        user_id: int,
        parse_mode: Optional[str] = None
    ) -> UISpecParsePipelineMixin:
        """创建解析管道实例"""
        return UISpecParsePipelineMixin(db, project_id, user_id, parse_mode=parse_mode)

    @staticmethod
    def encode_image_to_base64(image_path: str) -> Optional[str]:
        """同步的图片编码"""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"图片编码失败: {str(e)}")
            return None
