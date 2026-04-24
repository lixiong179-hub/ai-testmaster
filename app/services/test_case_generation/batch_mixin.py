"""
Test Case Generation Service - 批量生成Mixin
包含批量生成测试用例的流式输出逻辑
"""
from typing import List, Dict, Any, Optional, AsyncGenerator
from loguru import logger

from app.services.test_case_generation.base_mixin import ContentSanitizer


class TestCaseGenerationBatchMixin:
    """测试用例生成服务 - 批量生成Mixin"""

    async def generate_test_cases_batch(
        self,
        project_id: int,
        user_id: int,
        test_point_ids: Optional[List[int]] = None,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_page: int = 1,
        test_point_page_size: int = 100,
        case_type: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        批量生成测试用例

        Args:
            project_id: 项目ID
            user_id: 用户ID
            test_point_ids: 测试点ID列表
            requirement_file_ids: 需求文档文件ID列表
            ui_file_ids: UI原型图文件ID列表
            test_point_page: 测试点页码
            test_point_page_size: 测试点每页数量
            case_type: 用例类型（可选，不指定时由AI智能判断）

        Yields:
            生成进度和结果
        """
        yield {"progress": 5, "message": "获取上下文信息", "status": "running"}

        context = await self.get_context_for_generation(
            project_id=project_id,
            user_id=user_id,
            requirement_file_ids=requirement_file_ids,
            ui_file_ids=ui_file_ids,
            ui_screen_ids=ui_screen_ids,
            test_point_ids=test_point_ids,
            test_point_page=test_point_page,
            test_point_page_size=test_point_page_size
        )

        warnings = context.get("warnings", [])
        if warnings:
            for warning in warnings[:3]:
                yield {"progress": 5, "message": warning, "status": "warning"}

        test_points = context.get("test_points", [])
        total = len(test_points)

        if total == 0:
            yield {"progress": 100, "message": "没有找到测试点", "status": "warning", "data": []}
            return

        pagination = context.get("pagination", {})

        yield {
            "progress": 10,
            "message": f"开始生成{total}个测试用例",
            "status": "running",
            "total": total,
            "pagination": pagination
        }

        created_cases = []
        failed_count = 0

        primary_requirement_file_id = requirement_file_ids[0] if requirement_file_ids else None

        for i, test_point in enumerate(test_points):
            try:
                generated_case = await self.generate_test_case_for_point(
                    context=context,
                    test_point=test_point,
                    project_id=project_id,
                    case_type=case_type
                )

                case = await self._save_test_case(
                    project_id=project_id,
                    generated_case=generated_case,
                    test_point=test_point,
                    requirement_file_id=primary_requirement_file_id
                )
                created_cases.append(case)

                progress = int(10 + (i + 1) / total * 85)
                yield {
                    "progress": progress,
                    "message": f"已生成{i + 1}/{total}个测试用例",
                    "status": "running",
                    "current": i + 1,
                    "total": total,
                    "case": {
                        "id": case.id,
                        "title": ContentSanitizer.sanitize_for_log(case.title),
                        "module": case.module
                    }
                }

            except Exception as e:
                failed_count += 1
                logger.error(f"生成测试用例失败: {e}")
                yield {
                    "progress": int(10 + (i + 1) / total * 85),
                    "message": f"生成第{i + 1}个用例失败",
                    "status": "running",
                    "error": True,
                    "failed_count": failed_count
                }

        yield {
            "progress": 100,
            "message": f"完成！成功{len(created_cases)}个，失败{failed_count}个",
            "status": "success" if failed_count == 0 else "partial",
            "total": total,
            "created": len(created_cases),
            "failed": failed_count,
            "pagination": pagination,
            "cases": [
                {"id": c.id, "title": ContentSanitizer.sanitize_for_log(c.title)}
                for c in created_cases
            ]
        }
