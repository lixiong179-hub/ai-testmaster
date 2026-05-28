"""
Test Case Generation Service - 批量生成Mixin
包含批量生成测试用例的流式输出逻辑
"""
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from loguru import logger

from app.services.test_case_generation.base_mixin import ContentSanitizer


class TestCaseGenerationBatchMixin:
    """测试用例生成服务 - 批量生成Mixin"""

    _DEFAULT_AI_CONCURRENCY = 3

    def _get_ai_generation_concurrency(self) -> int:
        from app.core.config import settings
        value = int(getattr(settings, "AI_CASE_GENERATION_CONCURRENCY", self._DEFAULT_AI_CONCURRENCY))
        return max(1, value)

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
        concurrency = self._get_ai_generation_concurrency()
        semaphore = asyncio.Semaphore(concurrency)

        async def _generate_one(index: int, point: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    generated = await self.generate_test_case_for_point(
                        context=context,
                        test_point=point,
                        project_id=project_id,
                        case_type=case_type
                    )
                    return {
                        "index": index,
                        "test_point": point,
                        "generated_case": generated,
                        "error": None,
                    }
                except Exception as e:
                    logger.error(f"生成测试用例失败: {e}")
                    return {
                        "index": index,
                        "test_point": point,
                        "generated_case": None,
                        "error": e,
                    }

        yield {
            "progress": 10,
            "message": f"AI并发生成已启动，并发数{concurrency}",
            "status": "running",
            "total": total,
            "concurrency": concurrency,
        }

        generation_tasks = [
            asyncio.create_task(_generate_one(i, test_point))
            for i, test_point in enumerate(test_points)
        ]

        for completed, task in enumerate(asyncio.as_completed(generation_tasks), 1):
            result = await task
            i = result["index"]
            test_point = result["test_point"]
            generated_case = result["generated_case"]
            if result["error"] is not None or generated_case is None:
                failed_count += 1
                yield {
                    "progress": int(10 + completed / total * 85),
                    "message": f"生成第{i + 1}个用例失败",
                    "status": "running",
                    "error": True,
                    "failed_count": failed_count,
                    "current": completed,
                    "total": total,
                }
                continue

            try:
                candidate_cases = [generated_case]
                candidate_cases.extend(generated_case.get("_extra_cases", []))
                saved_cases_for_point = []
                skipped_count = 0

                for candidate_case in candidate_cases:
                    try:
                        saved_case = await self._save_test_case(
                            project_id=project_id,
                            generated_case=candidate_case,
                            test_point=test_point,
                            requirement_file_id=primary_requirement_file_id
                        )
                        created_cases.append(saved_case)
                        saved_cases_for_point.append(saved_case)
                    except Exception as save_e:
                        skipped_count += 1
                        failed_count += 1
                        logger.warning(f"case skipped by generation quality gate: {save_e}")

                progress = int(10 + completed / total * 85)
                case_payload = None
                if saved_cases_for_point:
                    first_saved = saved_cases_for_point[0]
                    case_payload = {
                        "id": first_saved.id,
                        "title": ContentSanitizer.sanitize_for_log(first_saved.title),
                        "module": first_saved.module
                    }
                yield {
                    "progress": progress,
                    "message": f"已生成{i + 1}/{total}个测试用例",
                    "status": "running",
                    "current": completed,
                    "total": total,
                    "case": case_payload,
                    "saved_count": len(saved_cases_for_point),
                    "skipped_count": skipped_count
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
