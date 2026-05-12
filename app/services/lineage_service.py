"""用例血缘查询服务模块

本模块提供用例血缘树的查询功能，包括祖先链追溯和后代子树遍历。
对应 plan §5.3 用例血缘 API。

核心函数概览：
    - get_lineage : 获取用例血缘树（祖先链 + 后代子树 + 链长度 + 警告）

依赖关系：
    - app.models.test_case : TestCase
    - app.services.config_service : LINEAGE_CHAIN_WARNING_LENGTH
"""
import logging
from typing import Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.test_case import TestCase

logger = logging.getLogger(__name__)

MAX_DESCENDANT_DEPTH = 10


class LineageNode(BaseModel):
    """血缘树节点。"""
    id: int
    case_no: str
    title: str
    lifecycle_status: str
    prior_quality_score: Optional[float] = None
    posterior_quality_score: Optional[float] = None
    parent_case_id: Optional[int] = None
    children: List["LineageNode"] = []

    class Config:
        from_attributes = True


class LineageResult(BaseModel):
    """血缘查询结果。"""
    root: LineageNode
    ancestors: List[LineageNode] = []
    chain_length: int = 0
    warning: Optional[str] = None


def get_lineage(db: Session, test_case_id: int) -> Optional[LineageResult]:
    """获取用例血缘树。

    从指定用例出发，向上追溯祖先链至根节点，向下遍历后代子树。
    当链长度 >= LINEAGE_CHAIN_WARNING_LENGTH 时返回警告。

    Args:
        db: 数据库会话。
        test_case_id: 用例 ID。

    Returns:
        LineageResult 或 None（用例不存在）。
    """
    case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if case is None:
        return None

    ancestors = _trace_ancestors(db, case)

    root = ancestors[0] if ancestors else _to_node(case)
    _build_descendant_tree(db, root)

    chain_length = len(ancestors) + 1
    warning = _check_chain_warning(chain_length)

    return LineageResult(
        root=root,
        ancestors=ancestors,
        chain_length=chain_length,
        warning=warning,
    )


def _trace_ancestors(db: Session, case: TestCase) -> List[LineageNode]:
    """向上追溯祖先链至根节点（parent_case_id == None 的节点）。

    使用单次批量查询加载所有祖先，避免 N+1 问题。

    Args:
        db: 数据库会话。
        case: 起始用例。

    Returns:
        祖先节点列表（从根到直接父节点），不含 case 本身。
    """
    ancestors: List[LineageNode] = []
    visited: set = {case.id}
    current_id = case.parent_case_id

    if current_id is None:
        return ancestors

    all_ancestors = (
        db.query(TestCase)
        .filter(TestCase.id != case.id)
        .all()
    )
    ancestor_map: Dict[int, TestCase] = {c.id: c for c in all_ancestors}

    while current_id is not None:
        if current_id in visited:
            logger.warning("血缘链检测到循环引用: case_id=%d", current_id)
            break
        visited.add(current_id)

        parent = ancestor_map.get(current_id)
        if parent is None:
            parent = db.query(TestCase).filter(TestCase.id == current_id).first()
            if parent is None:
                break
            ancestor_map[parent.id] = parent

        ancestors.append(_to_node(parent))
        current_id = parent.parent_case_id

    ancestors.reverse()
    return ancestors


def _build_descendant_tree(db: Session, node: LineageNode) -> None:
    """批量构建后代子树（一次性加载所有后代，内存中组装树）。

    使用单次查询加载所有后代用例，避免 N+1 问题。
    递归深度限制为 MAX_DESCENDANT_DEPTH，循环引用自动检测。

    Args:
        db: 数据库会话。
        node: 根节点（就地修改 children）。
    """
    all_descendants = (
        db.query(TestCase)
        .filter(TestCase.parent_case_id.isnot(None))
        .all()
    )

    children_map: Dict[int, List[TestCase]] = {}
    for desc in all_descendants:
        pid = desc.parent_case_id
        if pid is not None:
            children_map.setdefault(pid, []).append(desc)

    visited: set = set()

    def _build(node: LineageNode, depth: int) -> None:
        if depth > MAX_DESCENDANT_DEPTH:
            return
        if node.id in visited:
            return
        visited.add(node.id)

        for child_case in children_map.get(node.id, []):
            child_node = _to_node(child_case)
            node.children.append(child_node)
            _build(child_node, depth + 1)

    _build(node, 0)


def _to_node(case: TestCase) -> LineageNode:
    """将 TestCase ORM 对象转换为 LineageNode。"""
    return LineageNode(
        id=case.id,
        case_no=case.case_no,
        title=case.title,
        lifecycle_status=case.lifecycle_status,
        prior_quality_score=case.prior_quality_score,
        posterior_quality_score=case.posterior_quality_score,
        parent_case_id=case.parent_case_id,
    )


def _check_chain_warning(chain_length: int) -> Optional[str]:
    """检查链长度是否超过警告阈值。

    Args:
        chain_length: 血缘链长度。

    Returns:
        警告字符串或 None。
    """
    try:
        from app.services.config_service import get_config
        threshold = int(get_config("LINEAGE_CHAIN_WARNING_LENGTH", 3))
    except Exception:
        threshold = 3

    if chain_length >= threshold:
        return (
            f"血缘链长度 {chain_length} 已达警告阈值 {threshold}，"
            f"建议检查是否存在过度衍生"
        )
    return None
