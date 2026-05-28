"""上下文构建 - 测试点数据加载与文件内容提取
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

import json

from app.models.test_point import TestPoint
from app.models.test_case import TestCase
from app.models.project import ProjectFile
from app.crud import test_point as test_point_crud

DEFAULT_TEST_POINT_PAGE_SIZE = 100
MAX_TEST_POINT_PAGE_SIZE = 500


def load_test_points(
    db: Session,
    project_id: int,
    test_point_ids: Optional[List[int]] = None,
    page: int = 1,
    page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE
) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """加载测试点数据。

    加载策略:
        1. 指定test_point_ids -> 加载指定测试点
        2. 未指定 -> 分页查询项目测试点

    Args:
        db: 数据库会话。
        project_id: 项目ID。
        test_point_ids: 测试点ID列表，可选。
        page: 分页页码，默认1。
        page_size: 分页大小，默认100。

    Returns:
        (测试点列表, 分页信息（仅分页查询时）)
    """
    test_points = []
    pagination = None

    if test_point_ids:
        for point_id in test_point_ids:
            point = test_point_crud.get_test_point_by_id(db, point_id, project_id)
            if point:
                function = _extract_function_from_ai_prompt(point.ai_prompt)
                test_points.append({
                    "id": point.id, "module": point.module,
                    "function": function,
                    "point": point.point, "priority": point.priority
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
                "point": point.point, "priority": point.priority
            })
        pagination = {
            "page": page, "page_size": len(page_points),
            "total": total_count, "has_more": (skip + page_limit) < total_count,
            "uncovered_first": True,
            "covered_test_point_count": len(covered_test_point_ids),
        }

    return test_points, pagination


def _extract_function_from_ai_prompt(ai_prompt: Optional[str]) -> str:
    """从ai_prompt字段中提取function值。

    ai_prompt存储的是AI分析需求时返回的原始JSON字符串，
    其中可能包含function字段。如果提取失败则返回空字符串。

    Args:
        ai_prompt: AI分析时的提示词JSON字符串。

    Returns:
        function字段值，提取失败时返回空字符串。
    """
    if not ai_prompt:
        return ""
    try:
        data = json.loads(ai_prompt)
        if isinstance(data, dict):
            return str(data.get('function', '') or '')
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return ""


async def get_file_content_helper(
    db: Session,
    file: ProjectFile,
    force_refresh: bool = False
) -> Optional[str]:
    """获取文件内容，支持缓存和强制刷新。

    获取策略:
        1. 文件已提取完成且不强制刷新 -> 直接返回缓存内容
        2. 内容为空或提取状态为pending/failed -> 重新提取
        3. 提取失败 -> 返回现有内容（可能为空）

    Args:
        db: 数据库会话。
        file: ProjectFile ORM实例。
        force_refresh: 是否强制刷新，默认False。

    Returns:
        文件内容字符串，获取失败时返回None。
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
