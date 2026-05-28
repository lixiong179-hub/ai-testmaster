"""
Test Case Generation Service - 基础方法Mixin
包含内容清洗器、上下文获取、UI描述构建等基础能力
"""
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.test_point import TestPoint
from app.models.test_case import TestCase
from app.models.project import ProjectFile
from app.models.ui_prototype import UIPrototypeScreen
from app.crud import test_point as test_point_crud
from app.crud import file as file_crud
from app.services.test_case_generation.test_point_loader import _extract_function_from_ai_prompt
from app.services.file_content_extractor import get_file_content

DEFAULT_TEST_POINT_PAGE_SIZE = 100
MAX_TEST_POINT_PAGE_SIZE = 500

TEST_CATEGORY_UI_AUTO = "ui_automation"
TEST_CATEGORY_MANUAL = "manual"
TEST_CATEGORY_API_AUTO = "api_automation"


class ContentSanitizer:
    """
    内容清洗器 - 防止Prompt注入攻击
    对用户输入的内容进行清洗和转义，确保AI输出安全可靠
    """

    INJECTION_PATTERNS = [
        r'```system',
        r'```prompt',
        r'忽略.*指令',
        r'忽略.*规则',
        r'你是一个.*而不是',
        r'你现在是',
        r'/system',
        r'<system>',
        r'{{.*}}',
    ]

    @classmethod
    def sanitize(cls, content: str, max_length: int = 10000) -> str:
        """清洗内容，防止Prompt注入"""
        if not content:
            return ""
        content = re.sub(r'```(?:json|yaml|xml|markdown|prompt|system)', '', content, flags=re.IGNORECASE)
        content = re.sub(r'```', '', content)
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
        for pattern in cls.INJECTION_PATTERNS:
            content = re.sub(pattern, '[已过滤]', content, flags=re.IGNORECASE)
        if len(content) > max_length:
            content = content[:max_length] + f"\n\n[内容已截断，原长度: {len(content)}字符]"
        return content

    @classmethod
    def sanitize_for_log(cls, content: str, max_length: int = 200) -> str:
        """清洗内容用于日志记录（更严格的截断）"""
        if not content:
            return ""
        content = re.sub(r'[\n\r\t]+', ' ', content)
        if len(content) > max_length:
            return content[:max_length] + "..."
        return content


class TestCaseGenerationBaseMixin:
    """测试用例生成服务 - 基础方法Mixin"""

    def __init__(self, db: Session):
        self.db = db

    async def get_context_for_generation(
        self,
        project_id: int,
        user_id: int,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_ids: Optional[List[int]] = None,
        force_refresh: bool = False,
        test_point_page: int = 1,
        test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE
    ) -> Dict[str, Any]:
        """获取测试用例生成的上下文信息"""
        context = {
            "requirement_content": "",
            "ui_descriptions": [],
            "ui_specs": [],
            "test_points": [],
            "files_used": [],
            "warnings": [],
            "cache_info": {}
        }

        if requirement_file_ids:
            for file_id in requirement_file_ids:
                file_record = file_crud.get_file_by_id(self.db, file_id, project_id)
                if file_record and file_record.resource_type == "requirement":
                    content = file_record.content or ""
                    if force_refresh or not content:
                        content = await get_file_content(file_id)
                    if content:
                        context["requirement_content"] += f"\n\n【{file_record.file_name}】\n{content}"
                        context["files_used"].append(file_id)

        if not context["requirement_content"]:
            all_req_files = file_crud.get_project_files_by_type(self.db, project_id, "requirement")
            for file_record in all_req_files:
                content = file_record.content or ""
                if force_refresh or not content:
                    content = await get_file_content(file_record.id)
                if content:
                    context["requirement_content"] += f"\n\n【{file_record.file_name}】\n{content}"
                    context["files_used"].append(file_record.id)

        if ui_screen_ids:
            found_screen_ids = set()
            for screen_id in ui_screen_ids:
                screen = self.db.query(UIPrototypeScreen).filter(
                    UIPrototypeScreen.id == screen_id,
                    UIPrototypeScreen.project_id == project_id
                ).first()
                if screen:
                    found_screen_ids.add(screen.id)
                    ui_desc = {
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "prototype_name": screen.prototype_name,
                        "parse_status": screen.parse_status,
                        "summary": screen.summary or "",
                        "element_count": screen.element_count or 0,
                        "button_count": screen.button_count or 0,
                        "input_count": screen.input_count or 0,
                        "description": screen.summary or ""
                    }
                    if not screen.summary and screen.parse_status != "completed":
                        ui_desc["description"] = "该屏幕尚未完成AI解析，仅可基于页面名称和流程顺序生成基础用例"
                        context["warnings"].append(
                            f"屏幕「{screen.screen_name}」尚未完成解析，AI可用的UI元素信息有限"
                        )
                    context["ui_descriptions"].append(ui_desc)
                    if screen.ui_spec:
                        context["ui_specs"].append({
                            "screen_id": screen.id,
                            "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })
                else:
                    context["warnings"].append(f"未找到UI屏幕ID: {screen_id}")
            missing_count = len(set(ui_screen_ids) - found_screen_ids)
            if missing_count:
                context["warnings"].append(f"{missing_count}个UI屏幕未被纳入上下文")
        elif ui_file_ids:
            for file_id in ui_file_ids:
                file_record = file_crud.get_file_by_id(self.db, file_id, project_id)
                if file_record and file_record.resource_type == "ui_mockup":
                    ui_desc = {
                        "file_name": file_record.file_name,
                        "file_url": file_record.file_url,
                        "description": file_record.description or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    context["files_used"].append(file_id)

                    linked_screens = self.db.query(UIPrototypeScreen).filter(
                        UIPrototypeScreen.project_id == project_id,
                        UIPrototypeScreen.prototype_name == file_record.file_name,
                        UIPrototypeScreen.parse_status == "completed",
                        UIPrototypeScreen.ui_spec.isnot(None)
                    ).all()
                    for screen in linked_screens:
                        context["ui_specs"].append({
                            "screen_id": screen.id,
                            "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })

        if not context["ui_descriptions"] and not context["ui_specs"]:
            screens_with_spec = self.db.query(UIPrototypeScreen).filter(
                UIPrototypeScreen.project_id == project_id,
                UIPrototypeScreen.parse_status == "completed",
                UIPrototypeScreen.ui_spec.isnot(None)
            ).order_by(UIPrototypeScreen.screen_order).all()

            if screens_with_spec:
                for screen in screens_with_spec:
                    ui_desc = {
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "prototype_name": screen.prototype_name,
                        "parse_status": screen.parse_status,
                        "summary": screen.summary or "",
                        "element_count": screen.element_count or 0,
                        "button_count": screen.button_count or 0,
                        "input_count": screen.input_count or 0,
                        "description": screen.summary or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    if screen.ui_spec:
                        context["ui_specs"].append({
                            "screen_id": screen.id,
                            "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })
            else:
                all_ui_files = file_crud.get_project_files_by_type(self.db, project_id, "ui_mockup")
                for file_record in all_ui_files:
                    ui_desc = {
                        "file_name": file_record.file_name,
                        "file_url": file_record.file_url,
                        "description": file_record.description or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    context["files_used"].append(file_record.id)

        if test_point_ids:
            for point_id in test_point_ids:
                point = test_point_crud.get_test_point_by_id(self.db, point_id, project_id)
                if point:
                    context["test_points"].append({
                        "id": point.id,
                        "module": point.module,
                        "function": _extract_function_from_ai_prompt(point.ai_prompt),
                        "point": point.point,
                        "priority": point.priority
                    })
        else:
            skip = (test_point_page - 1) * test_point_page_size
            page_limit = min(test_point_page_size, MAX_TEST_POINT_PAGE_SIZE)
            covered_test_point_ids = {
                row[0]
                for row in self.db.query(TestCase.test_point_id)
                .filter(
                    TestCase.project_id == project_id,
                    TestCase.is_deleted == False,  # noqa: E712
                    TestCase.generate_status == 1,
                    TestCase.test_point_id.isnot(None),
                )
                .distinct()
                .all()
                if row[0] is not None
            }
            all_points = self.db.query(TestPoint).filter(
                TestPoint.project_id == project_id
            ).all()
            total_count = len(all_points)
            all_points.sort(
                key=lambda point: (
                    point.id in covered_test_point_ids,
                    point.priority or 99,
                    point.id,
                )
            )
            page_points = all_points[skip: skip + page_limit]

            for point in page_points:
                context["test_points"].append({
                    "id": point.id,
                    "module": point.module,
                    "function": _extract_function_from_ai_prompt(point.ai_prompt),
                    "point": point.point,
                    "priority": point.priority
                })

            context["pagination"] = {
                "page": test_point_page,
                "page_size": len(page_points),
                "total": total_count,
                "has_more": (skip + page_limit) < total_count,
                "uncovered_first": True,
                "covered_test_point_count": len(covered_test_point_ids)
            }

        return context

    async def _get_file_content(self, file: ProjectFile, force_refresh: bool = False) -> Optional[str]:
        """获取文件内容（支持自动提取）"""
        if file.content and file.extract_status == 'completed' and not force_refresh:
            return file.content
        if not file.content or file.extract_status in ['pending', 'failed']:
            from app.services.file_content_extractor import FileContentExtractor
            extractor = FileContentExtractor(self.db)
            result = await extractor.extract_file_content(file, force_refresh)
            if result.get("success"):
                return result.get("content") or ""
        return file.content

    def _build_ui_description(self, ui_descriptions: List[Dict[str, Any]]) -> str:
        """构建UI描述文本"""
        if not ui_descriptions:
            return ""
        parts = []
        for ui_desc in ui_descriptions:
            if ui_desc.get("screen_name"):
                name = ui_desc["screen_name"]
                summary = ui_desc.get("summary", "")
                element_count = ui_desc.get("element_count", 0)
                button_count = ui_desc.get("button_count", 0)
                input_count = ui_desc.get("input_count", 0)
                desc_parts = [f"【{name}】"]
                if summary:
                    desc_parts.append(f"功能：{summary}")
                if element_count:
                    desc_parts.append(f"元素：{element_count}个（按钮{button_count}个，输入框{input_count}个）")
                parts.append("\n".join(desc_parts))
            else:
                name = ui_desc.get("screen_name") or ui_desc.get("file_name") or ui_desc.get("name", "未命名")
                file_id = ui_desc.get("file_id", "")
                content = ui_desc.get("content", "")
                description = ui_desc.get("description", "")
                if content:
                    parts.append(f"【{name}】\n{content}")
                elif description:
                    parts.append(f"【{name}】\n{description}")
                else:
                    parts.append(f"【{name}】(文件ID: {file_id}，内容待提取)")
        return "\n\n".join(parts)
