"""UI解析Mixin - 实现UI原型图的AI解析与结构化。
"""
import os
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from app.crud import ui_prototype as ui_prototype_crud


class UISpecParseMixin:
    async def parse_screen(self, screen_id: int) -> Tuple[bool, str]:
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
                ui_prototype_crud.update_ui_screen_parse_result(
                    db=self.db,
                    screen_id=screen_id,
                    ui_spec=ui_spec,
                    parse_model=self.parser.vision_model.model_name,
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
                ui_prototype_crud.update_ui_screen_parse_status(self.db, screen_id, "failed", error)
                return False, error
        except Exception as e:
            logger.error(f"解析屏幕失败: {e}")
            ui_prototype_crud.update_ui_screen_parse_status(self.db, screen_id, "failed", str(e))
            return False, "解析失败"

    async def batch_parse_screens(
        self,
        screen_ids: List[int],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
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
