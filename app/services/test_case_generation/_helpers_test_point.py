"""test_case_generation 测试点加载与文件内容获取。

加载测试点数据（指定 ID 或分页+未覆盖优先排序），并获取项目文件内容
（支持缓存与强制刷新）。
"""
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.crud import test_point as test_point_crud
from app.models.project import ProjectFile
from app.models.test_case import TestCase
from app.models.test_point import TestPoint

from app.services.test_case_generation._helpers_constants import (
    DEFAULT_TEST_POINT_PAGE_SIZE,
    MAX_TEST_POINT_PAGE_SIZE,
)
from app.services.test_case_generation._helpers_text import _extract_function_from_ai_prompt


# ── 测试点加载 ──
def load_test_points(
    db: Session,
    project_id: int,
    test_point_ids: Optional[List[int]] = None,
    page: int = 1,
    page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """加载测试点数据。

    加载策略：
        1. 指定 test_point_ids -> 加载指定测试点
        2. 未指定 -> 分页查询项目测试点（未覆盖优先排序）
    """
    test_points: List[Dict[str, Any]] = []
    pagination: Optional[Dict[str, Any]] = None

    if test_point_ids:
        for point_id in test_point_ids:
            point = test_point_crud.get_test_point_by_id(db, point_id, project_id)
            if point:
                function = _extract_function_from_ai_prompt(point.ai_prompt)
                test_points.append({
                    "id": point.id, "module": point.module,
                    "function": function,
                    "point": point.point, "priority": point.priority,
                })
    else:
        skip = (page - 1) * page_size
        page_limit = min(page_size, MAX_TEST_POINT_PAGE_SIZE)
        covered_test_point_ids = {
            row[0]
            for row in db.query(TestCase.test_point_id)
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
        all_points = db.query(TestPoint).filter(
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
            function = _extract_function_from_ai_prompt(point.ai_prompt)
            test_points.append({
                "id": point.id, "module": point.module,
                "function": function,
                "point": point.point, "priority": point.priority,
            })
        pagination = {
            "page": page, "page_size": len(page_points),
            "total": total_count, "has_more": (skip + page_limit) < total_count,
            "uncovered_first": True,
            "covered_test_point_count": len(covered_test_point_ids),
        }

    return test_points, pagination


async def get_file_content_helper(
    db: Session,
    file: ProjectFile,
    force_refresh: bool = False,
) -> Optional[str]:
    """获取文件内容，支持缓存和强制刷新。

    策略：
        1. 已提取完成且不强制刷新 -> 返回缓存
        2. 内容为空或状态 pending/failed -> 重新提取
        3. 提取失败 -> 返回现有内容
    """
    if file.content and file.extract_status == 'completed' and not force_refresh:
        return file.content
    if not file.content or file.extract_status in ['pending', 'failed']:
        from app.services.file_content_extractor import FileContentExtractor
        extractor = FileContentExtractor(db)
        result = await extractor.extract_file_content(file, force_refresh)
        if result.get("success"):
            return result.get("content") or ""
    return file.content
