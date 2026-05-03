"""
用例生命周期状态机服务

集中管理 TestCase lifecycle_status 的合法迁移，所有变更必经此服务。
覆盖 plan §4.2 完整迁移规则。

核心类/函数概览：
    - IllegalStateTransition : 非法状态迁移异常
    - MissingReviewError : 缺少评审ID异常
    - CooldownNotElapsedError : 冷却时间未满异常
    - MissingDeprecateReasonError : 缺少废弃原因异常
    - can_transition(from_status, to_status) -> bool : 判断迁移是否合法
    - transition(db, case_id, to_status, ...) -> TestCase : 执行状态迁移

迁移规则（与 plan §4.2 一致）：
    draft → pending_review          : AI 生成完成
    pending_review → active         : 人工评审通过（或先验分 ≥ AUTO_APPROVE_MIN_GRADE 自动通过）
    pending_review → needs_modify   : 人工评审否决
    pending_review → deprecated     : 人工判定无价值，需 deprecate_reason
    active → needs_modify           : 必须附带 last_review_id
    active → locator_broken         : UI 变更导致 locator 失效
    active → deprecated             : 需 deprecate_reason + review_id
    needs_modify → pending_review   : 创建新 case 版本，旧 case → archived
    locator_broken → active         : 重录验证通过
    locator_broken → deprecated     : 需 deprecate_reason
    deprecated → archived           : 冷却 ≥ LIFECYCLE_DEPRECATE_COOLDOWN_HOURS

全局约束：
    1. 只能由本服务驱动迁移，禁止直接 SQL update
    2. 所有迁移产生 audit_log 记录
    3. archived 是终态，不可恢复（要恢复则复制为新用例 draft）

依赖关系：
    - app.models.enums.TestCaseLifecycleStatus : 状态枚举
    - app.models.test_case.TestCase : ORM 模型
    - app.core.config.settings : 配置项
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.enums import TestCaseLifecycleStatus
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.core.config import settings

logger = logging.getLogger(__name__)


# ==================== 迁移规则表 ====================
# 键: (from_status, to_status)，值: dict 描述前置条件和附加动作
TRANSITION_RULES: dict[tuple[str, str], dict] = {
    (TestCaseLifecycleStatus.DRAFT.value, TestCaseLifecycleStatus.PENDING_REVIEW.value): {
        "requires": [],
        "description": "AI 生成完成，提交审核",
    },
    (TestCaseLifecycleStatus.PENDING_REVIEW.value, TestCaseLifecycleStatus.ACTIVE.value): {
        "requires": [],
        "description": "人工评审通过（或先验分自动通过）",
    },
    (TestCaseLifecycleStatus.PENDING_REVIEW.value, TestCaseLifecycleStatus.NEEDS_MODIFY.value): {
        "requires": [],
        "description": "人工评审否决，需修改",
    },
    (TestCaseLifecycleStatus.PENDING_REVIEW.value, TestCaseLifecycleStatus.DEPRECATED.value): {
        "requires": ["deprecate_reason"],
        "description": "人工判定无价值，废弃",
    },
    (TestCaseLifecycleStatus.ACTIVE.value, TestCaseLifecycleStatus.NEEDS_MODIFY.value): {
        "requires": ["review_id"],
        "description": "评审决定需修改",
    },
    (TestCaseLifecycleStatus.ACTIVE.value, TestCaseLifecycleStatus.LOCATOR_BROKEN.value): {
        "requires": [],
        "description": "UI 变更导致 locator 失效",
    },
    (TestCaseLifecycleStatus.ACTIVE.value, TestCaseLifecycleStatus.DEPRECATED.value): {
        "requires": ["deprecate_reason", "review_id"],
        "description": "废弃，需原因 + 评审",
    },
    (TestCaseLifecycleStatus.NEEDS_MODIFY.value, TestCaseLifecycleStatus.PENDING_REVIEW.value): {
        "requires": [],
        "description": "创建新版本提交审核",
        "side_effect": "archive_old_version",
    },
    (TestCaseLifecycleStatus.LOCATOR_BROKEN.value, TestCaseLifecycleStatus.ACTIVE.value): {
        "requires": [],
        "description": "重录验证通过",
    },
    (TestCaseLifecycleStatus.LOCATOR_BROKEN.value, TestCaseLifecycleStatus.DEPRECATED.value): {
        "requires": ["deprecate_reason"],
        "description": "定位失效后废弃",
    },
    (TestCaseLifecycleStatus.DEPRECATED.value, TestCaseLifecycleStatus.ARCHIVED.value): {
        "requires": [],
        "description": "冷却期满，归档",
        "cooldown_hours": True,
    },
}

# 合法目标状态集合（用于 can_transition 快速判断）
_VALID_TRANSITIONS: dict[str, set[str]] = {}
for (_from, _to), _rule in TRANSITION_RULES.items():
    _VALID_TRANSITIONS.setdefault(_from, set()).add(_to)


# ==================== 异常定义 ====================

class IllegalStateTransition(ValueError):
    """非法状态迁移：from → to 不在 TRANSITION_RULES 中"""

    def __init__(self, from_status: str, to_status: str, detail: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        msg = f"Illegal transition: {from_status} → {to_status}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


class MissingReviewError(ValueError):
    """缺少评审ID：active → needs_modify / active → deprecated 必须附带 review_id"""

    def __init__(self, transition: str):
        super().__init__(f"Transition '{transition}' requires review_id")


class CooldownNotElapsedError(ValueError):
    """冷却时间未满：deprecated → archived 需等待 LIFECYCLE_DEPRECATE_COOLDOWN_HOURS"""

    def __init__(self, remaining_hours: float):
        self.remaining_hours = remaining_hours
        super().__init__(
            f"Cooldown not elapsed, {remaining_hours:.1f} hours remaining"
        )


class MissingDeprecateReasonError(ValueError):
    """缺少废弃原因：涉及 deprecated 的迁移必须提供 deprecate_reason"""

    def __init__(self, transition: str):
        super().__init__(f"Transition '{transition}' requires deprecate_reason")


# ==================== 公开接口 ====================

def can_transition(from_status: str, to_status: str) -> bool:
    """判断从 from_status 到 to_status 的迁移是否合法。

    Args:
        from_status: 当前状态值。
        to_status: 目标状态值。

    Returns:
        True 表示合法迁移路径存在，False 表示非法。
    """
    return to_status in _VALID_TRANSITIONS.get(from_status, set())


def transition(
    db: Session,
    case_id: int,
    to_status: str,
    *,
    review_id: Optional[int] = None,
    reason: Optional[str] = None,
    actor_id: Optional[int] = None,
    modification_hint: Optional[str] = None,
    auto_approve: bool = False,
) -> TestCase:
    """执行用例生命周期状态迁移。

    所有 lifecycle_status 变更必须通过此函数，禁止直接 SQL update。
    函数会校验迁移合法性、前置条件、冷却时间等，通过后更新用例状态。

    Args:
        db: 数据库会话。
        case_id: 用例 ID。
        to_status: 目标状态值（必须是 TestCaseLifecycleStatus 枚举值）。
        review_id: 评审 ID（部分迁移必填）。
        reason: 废弃原因（部分迁移必填）。
        actor_id: 操作人 ID（用于审计日志）。
        modification_hint: 修改提示（pending_review → needs_modify 等可选）。
        auto_approve: 是否自动通过（pending_review → active 时由先验分判定）。

    Returns:
        更新后的 TestCase 实例。

    Raises:
        IllegalStateTransition: 迁移路径不存在。
        MissingReviewError: 缺少必填的 review_id。
        MissingDeprecateReasonError: 缺少必填的 deprecate_reason。
        CooldownNotElapsedError: deprecated → archived 冷却时间未满。
        ValueError: 用例不存在或状态无效。
    """
    # 1. 查找用例
    test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
    if test_case is None:
        raise ValueError(f"TestCase id={case_id} not found")

    from_status = test_case.lifecycle_status

    # 2. 校验迁移路径合法性
    if not can_transition(from_status, to_status):
        raise IllegalStateTransition(from_status, to_status)

    rule = TRANSITION_RULES[(from_status, to_status)]
    requires = rule.get("requires", [])

    # 3. 校验必填参数
    if "review_id" in requires and review_id is None:
        raise MissingReviewError(f"{from_status} → {to_status}")

    if "deprecate_reason" in requires and not reason:
        raise MissingDeprecateReasonError(f"{from_status} → {to_status}")

    # 4. pending_review → active 时校验 auto_approve 资格
    #    M1 阶段：auto_approve=True 表示调用方已确认先验分 ≥ AUTO_APPROVE_MIN_GRADE
    #    后续可接入实际先验分计算逻辑
    if (
        from_status == TestCaseLifecycleStatus.PENDING_REVIEW.value
        and to_status == TestCaseLifecycleStatus.ACTIVE.value
        and not auto_approve
    ):
        # 非自动通过时，需要人工确认（当前仅记录日志，不阻断）
        # 后续 M2 可增加审批流程校验
        logger.info(
            "pending_review → active: manual approval, case_id=%d, actor_id=%s",
            case_id, actor_id,
        )

    # 5. 校验冷却时间
    if rule.get("cooldown_hours"):
        _check_cooldown(test_case)

    # 6. 执行迁移
    old_status = from_status
    try:
        enable_lifecycle_transition()
        test_case.lifecycle_status = to_status

        # 附加动作：记录 review_id
        if review_id is not None:
            test_case.last_review_id = review_id

        # 附加动作：进入 deprecated 时记录 deprecated_at 时间戳
        if to_status == TestCaseLifecycleStatus.DEPRECATED.value:
            test_case.deprecated_at = datetime.now(timezone.utc)

        # 附加动作：needs_modify → pending_review 时，旧版本归档
        if rule.get("side_effect") == "archive_old_version":
            test_case.lifecycle_status = TestCaseLifecycleStatus.ARCHIVED.value
            _create_new_version_case(db, test_case, modification_hint, actor_id)

        db.flush()
    finally:
        disable_lifecycle_transition()

    # 7. 写入审计日志（M1-T16 完成后自动生效，当前为预留接口）
    _write_audit_log(
        db=db,
        case_id=case_id,
        old_status=old_status,
        new_status=test_case.lifecycle_status,
        review_id=review_id,
        reason=reason,
        actor_id=actor_id,
        modification_hint=modification_hint,
        auto_approve=auto_approve,
    )

    return test_case


# ==================== 内部函数 ====================

def _check_cooldown(test_case: TestCase) -> None:
    """检查 deprecated → archived 的冷却时间。

    从用例进入 deprecated 状态的时刻算起，必须经过
    LIFECYCLE_DEPRECATE_COOLDOWN_HOURS 小时才能归档。

    优先使用 deprecated_at 字段（由 transition() 在进入 deprecated 时设置），
    对旧数据回退到 update_time / create_time。

    Raises:
        CooldownNotElapsedError: 冷却时间未满。
    """
    deprecated_at = test_case.deprecated_at or test_case.update_time or test_case.create_time
    if deprecated_at is None:
        # 无时间信息时允许归档（兼容旧数据）
        return

    # 兼容 MySQL 返回字符串类型的 datetime
    if isinstance(deprecated_at, str):
        deprecated_at = datetime.fromisoformat(deprecated_at)

    cooldown_hours = settings.LIFECYCLE_DEPRECATE_COOLDOWN_HOURS
    now = datetime.now(timezone.utc)
    # 确保 deprecated_at 是 timezone-aware 以便比较
    if deprecated_at.tzinfo is None:
        deprecated_at = deprecated_at.replace(tzinfo=timezone.utc)
    elapsed = now - deprecated_at
    required = timedelta(hours=cooldown_hours)

    if elapsed < required:
        remaining = required - elapsed
        remaining_hours = remaining.total_seconds() / 3600
        raise CooldownNotElapsedError(remaining_hours)


def _create_new_version_case(
    db: Session,
    old_case: TestCase,
    modification_hint: Optional[str],
    actor_id: Optional[int],
) -> None:
    """needs_modify → 新版本时，创建新用例（pending_review），旧用例归档。

    新用例的 parent_case_id 指向旧用例，形成血缘链。
    case_no 基于血缘链深度动态生成版本号，避免重复。

    Args:
        db: 数据库会话。
        old_case: 旧用例实例。
        modification_hint: 修改提示。
        actor_id: 操作人 ID。
    """
    # 🔴#2: 动态计算版本号 — 查询血缘链中已有版本数
    existing_versions = db.query(TestCase).filter(
        TestCase.parent_case_id == old_case.id
    ).count()
    # 也检查旧用例自身是否是某个父用例的子版本（追溯血缘链根节点）
    root_case_id = old_case.id
    root_case = old_case
    while root_case.parent_case_id is not None:
        parent = db.query(TestCase).filter(TestCase.id == root_case.parent_case_id).first()
        if parent is None:
            break
        root_case = parent
        root_case_id = root_case.id
    # 统计从根节点出发的所有子版本数（含当前旧用例的所有子版本）
    total_versions = db.query(TestCase).filter(
        (TestCase.parent_case_id == root_case_id) | (TestCase.id == root_case_id)
    ).count()
    next_version = total_versions + 1

    # 从根用例的 case_no 推导基础编号
    base_no = root_case.case_no
    # 如果根 case_no 已含 -vN 后缀，去掉后缀
    if "-v" in base_no:
        base_no = base_no.rsplit("-v", 1)[0]
    new_case_no = f"{base_no}-v{next_version}"

    new_case = TestCase(
        project_id=old_case.project_id,
        case_no=new_case_no,
        module=old_case.module,
        title=old_case.title,
        precondition=old_case.precondition,
        steps_json=old_case.steps_json,
        expected_result=old_case.expected_result,
        priority=old_case.priority,
        case_type=old_case.case_type,
        exec_script=old_case.exec_script,
        test_category=old_case.test_category,
        generate_status=old_case.generate_status,
        lifecycle_status=TestCaseLifecycleStatus.PENDING_REVIEW.value,
        test_point_id=old_case.test_point_id,
        summary=old_case.summary,
        summary_version=old_case.summary_version,  # 🔴#3: 继承摘要版本
        summary_model_version=old_case.summary_model_version,
        parent_case_id=old_case.id,
    )
    # 🔴#4: 在 guard 保护下 db.add，避免 before_flush 拦截
    # （新实例 lifecycle_status 是初始值，history 无 deleted/added，理论上不触发 guard，
    #   但显式保护更安全，且与 transition() 的 enable/disable 语义一致）
    db.add(new_case)
    db.flush()


def _write_audit_log(
    db: Session,
    case_id: int,
    old_status: str,
    new_status: str,
    review_id: Optional[int],
    reason: Optional[str],
    actor_id: Optional[int],
    modification_hint: Optional[str],
    auto_approve: bool,
) -> None:
    """写入审计日志。

    通过 audit_service.log_action 写入不可变审计记录。
    写入失败不阻塞业务流程（catch 异常仅打印日志）。
    """
    detail = {
        "from": old_status,
        "to": new_status,
        "auto_approve": auto_approve,
    }
    if review_id is not None:
        detail["review_id"] = review_id
    if reason is not None:
        detail["reason"] = reason
    if modification_hint is not None:
        detail["modification_hint"] = modification_hint

    try:
        from app.services.audit_service import log_action
        log_action(
            db=db,
            action="lifecycle_transition",
            actor_id=actor_id,
            target_kind="test_case",
            target_id=case_id,
            detail=detail,
        )
    except Exception as e:
        logger.error(
            "Failed to write audit log for lifecycle_transition: "
            "case_id=%d, %s → %s, error=%s",
            case_id, old_status, new_status, e,
        )
