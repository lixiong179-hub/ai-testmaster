"""项目历史高质量用例共享缓存层（Task 13: P2-2 重复查询消除）。

业务原因：domain_examples 与未来的评分混入逻辑均需查询同项目历史高质量用例，
通过请求级缓存避免同项目多次调用重复查询 DB，消除 N+1 查询风险。

缓存策略：
    - 模块级 dict 缓存，以 (project_id, min_score, limit) 为 key
    - 存储序列化后的 dict 列表（非 ORM 对象），避免 session 关闭后
      detached 实例问题
    - TTL 机制：缓存条目 5 分钟自动过期，避免长期运行脏数据
    - clear_history_cache() 供测试用例执行后或批量任务结束后清理
    - invalidate_project_cache(project_id) 精准失效单项目缓存

使用示例：
    from app.services.case_quality.history_cache import (
        get_history_cases_for_project,
        clear_history_cache,
    )
    cases = get_history_cases_for_project(db, project_id, min_score=80.0, limit=3)
    # ... 使用 cases ...
    clear_history_cache()  # 清理缓存
"""
import copy
import logging
import time
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 缓存 TTL（秒）：5 分钟，避免长期运行脏数据
_HISTORY_CACHE_TTL_SECONDS = 300

# 模块级缓存：key=(project_id, min_score, limit) -> (序列化用例 dict 列表, 创建时间戳)
# 使用显式 dict 而非 lru_cache，因 db session 不可哈希且会关闭，
# 缓存序列化后的 dict 列表可安全跨 session 边界使用
_history_cache: Dict[Tuple[Any, ...], Tuple[List[Dict[str, Any]], float]] = {}


def get_history_cases_for_project(
    db: Session,
    project_id: int,
    min_score: float = 80.0,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """获取项目历史高质量用例，带 TTL 缓存。

    业务原因：domain_examples 和评分混入逻辑重复查询同项目历史高质量用例，
    通过缓存层避免同项目多次调用重复查询 DB。

    缓存命中且未过期时直接返回已序列化的 dict 列表，不触发 DB 查询；
    未命中或已过期时执行 DB 查询并将结果序列化后存入缓存。

    Args:
        db: 数据库会话，仅用于未命中时的实际查询。
        project_id: 项目 ID。
        min_score: 最低质量分阈值，默认 80.0（对应 domain_examples 的 A 级门槛）。
        limit: 返回数量上限，默认 10。

    Returns:
        历史高质量用例的 dict 列表，每项包含 id/title/precondition/
        steps_json/expected_result/case_category/prior_quality_score 字段。
        无匹配数据时返回空列表。

    Note:
        返回的列表及其内部 dict 均为深拷贝，调用方修改不会污染缓存原始数据。
    """
    cache_key = (project_id, min_score, limit)
    entry = _history_cache.get(cache_key)
    if entry is not None:
        cases, created_at = entry
        # TTL 检查：过期则删除并重新查询
        if time.monotonic() - created_at <= _HISTORY_CACHE_TTL_SECONDS:
            logger.debug(f"history_cache 命中: project_id={project_id}, key={cache_key}")
            # 深拷贝切断共享引用：调用方修改返回值不应污染缓存
            return copy.deepcopy(cases)
        logger.debug(f"history_cache 过期: project_id={project_id}, key={cache_key}")
        _history_cache.pop(cache_key, None)

    cases = _query_history_cases(db, project_id, min_score, limit)
    _history_cache[cache_key] = (cases, time.monotonic())
    logger.debug(
        f"history_cache 未命中，已查询并缓存: project_id={project_id}, "
        f"count={len(cases)}, key={cache_key}"
    )
    # 首次写入后返回也用深拷贝，保持与缓存命中路径一致的语义
    return copy.deepcopy(cases)


def clear_history_cache() -> None:
    """清空历史用例缓存。

    业务原因：模块级缓存会跨请求/跨测试持久化，测试用例执行后或批量任务
    结束后必须调用此方法清理，避免脏数据污染后续调用。
    """
    _history_cache.clear()


def invalidate_project_cache(project_id: int) -> int:
    """精准失效单项目的所有缓存条目。

    业务原因：clear_history_cache 会清空所有项目缓存，影响范围过大。
    保存用例后只需失效当前项目的缓存，避免影响其他项目。

    Args:
        project_id: 需要失效缓存的项目 ID。

    Returns:
        被移除的缓存条目数。
    """
    keys_to_remove = [key for key in _history_cache if key[0] == project_id]
    for key in keys_to_remove:
        _history_cache.pop(key, None)
    if keys_to_remove:
        logger.debug(
            f"history_cache 精准失效: project_id={project_id}, "
            f"removed={len(keys_to_remove)}"
        )
    return len(keys_to_remove)


def _query_history_cases(
    db: Session,
    project_id: int,
    min_score: float,
    limit: int,
) -> List[Dict[str, Any]]:
    """执行实际 DB 查询并序列化结果（从 domain_examples.py 提取）。

    查询条件：
        - project_id 匹配
        - prior_quality_score >= min_score
        - is_deleted == False（未软删除）
        - steps_json IS NOT NULL（有可执行步骤）
    排序：prior_quality_score 降序（取质量最高的）
    限制：limit 条

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        min_score: 最低质量分阈值。
        limit: 返回数量上限。

    Returns:
        序列化后的用例 dict 列表。
    """
    from app.models.test_case import TestCase

    cases = (
        db.query(TestCase)
        .filter(
            TestCase.project_id == project_id,
            TestCase.prior_quality_score >= min_score,
            TestCase.is_deleted == False,  # noqa: E712
            TestCase.steps_json.isnot(None),
        )
        .order_by(TestCase.prior_quality_score.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_case(case) for case in cases]


def _serialize_case(case: Any) -> Dict[str, Any]:
    """将 ORM 用例对象序列化为字典。

    业务原因：缓存需跨 session 边界使用，ORM 对象在 session 关闭后变为
    detached 实例，访问属性可能抛 DetachedInstanceError。序列化为 dict
    后可安全缓存。

    Args:
        case: TestCase ORM 对象。

    Returns:
        包含用例关键字段的 dict。
    """
    return {
        "id": case.id,
        "title": case.title,
        "precondition": case.precondition,
        "steps_json": case.steps_json,
        "expected_result": case.expected_result,
        "case_category": case.case_category,
        "prior_quality_score": case.prior_quality_score,
    }
