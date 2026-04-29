"""
M1-T05 LifecycleService 状态机单元测试

覆盖范围：
1. 所有合法迁移路径（每条至少一例）
2. 所有非法迁移（应抛 IllegalStateTransition）
3. active → needs_modify 不带 review_id 抛错
4. active → deprecated 不带 deprecate_reason 抛错
5. pending_review → active 模拟人工通过
6. pending_review → needs_modify 记录 modification_hint
7. needs_modify → 新版本 必须创建新 case 版本
8. deprecated → archived 24h 内拒绝
9. 直接 SQL UPDATE lifecycle_status 触发 event hook 抛错
10. can_transition 正确性
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.enums import TestCaseLifecycleStatus
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.models.project import Project
from app.models.user import User
from app.models.code_review import CodeReview
from app.services.lifecycle_service import (
    can_transition,
    transition,
    IllegalStateTransition,
    MissingReviewError,
    CooldownNotElapsedError,
    MissingDeprecateReasonError,
    TRANSITION_RULES,
)


# ==================== Fixtures ====================

@pytest.fixture
def test_user(db):
    user = User(username="lc_test_user", email="lc_test@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    db.refresh(user)
    yield user
    # 清理顺序：先删 CodeReview（FK 引用 user），再删 TestCase/Project/User
    db.query(CodeReview).filter(
        (CodeReview.reviewer_id == user.id) | (CodeReview.author_id == user.id)
    ).delete(synchronize_session=False)
    db.query(TestCase).filter(TestCase.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.flush()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="LC测试项目", user_id=test_user.id)
    db.add(project)
    db.flush()
    db.refresh(project)
    yield project


def _create_case(db, project_id, lifecycle_status="active", **kwargs):
    """辅助函数：创建指定状态的 TestCase"""
    case = TestCase(
        project_id=project_id,
        case_no=kwargs.get("case_no", f"LC-{datetime.now().strftime('%H%M%S%f')}"),
        module="测试模块",
        title="生命周期测试用例",
        precondition="前置",
        steps_json=[],
        expected_result="预期",
        priority=1,
        case_type="UI",
        lifecycle_status=lifecycle_status,
    )
    # 需要通过 guard 设置 lifecycle_status
    enable_lifecycle_transition()
    try:
        db.add(case)
        db.flush()
        db.refresh(case)
    finally:
        disable_lifecycle_transition()
    return case


def _create_review(db, test_user_id):
    """辅助函数：创建 CodeReview 记录，满足 FK 约束"""
    review = CodeReview(
        title="LC测试评审",
        repository="https://example.com/repo",
        branch="main",
        reviewer_id=test_user_id,
        author_id=test_user_id,
    )
    db.add(review)
    db.flush()
    db.refresh(review)
    return review


# ==================== can_transition 测试 ====================

class TestCanTransition:
    """测试 can_transition 判断逻辑"""

    def test_all_legal_transitions(self):
        """所有合法迁移路径返回 True"""
        for (from_s, to_s) in TRANSITION_RULES:
            assert can_transition(from_s, to_s) is True, f"{from_s} → {to_s} should be legal"

    def test_archived_is_terminal(self):
        """archived 是终态，不可迁移到任何状态"""
        for status in TestCaseLifecycleStatus:
            assert can_transition("archived", status.value) is False

    def test_self_transition_not_allowed(self):
        """同状态迁移不允许"""
        for status in TestCaseLifecycleStatus:
            assert can_transition(status.value, status.value) is False

    def test_illegal_transitions(self):
        """部分典型非法迁移"""
        illegal = [
            ("active", "draft"),
            ("active", "pending_review"),
            ("draft", "active"),
            ("draft", "archived"),
            ("deprecated", "active"),
            ("deprecated", "needs_modify"),
            ("locator_broken", "pending_review"),
            ("locator_broken", "needs_modify"),
            ("needs_modify", "active"),
            ("needs_modify", "deprecated"),
            ("needs_modify", "archived"),
        ]
        for from_s, to_s in illegal:
            assert can_transition(from_s, to_s) is False, f"{from_s} → {to_s} should be illegal"


# ==================== 合法迁移路径测试 ====================

class TestLegalTransitions:
    """所有合法迁移路径，每条至少一例"""

    def test_draft_to_pending_review(self, db, test_project):
        tc = _create_case(db, test_project.id, lifecycle_status="draft")
        result = transition(db, tc.id, "pending_review")
        assert result.lifecycle_status == "pending_review"

    def test_pending_review_to_active(self, db, test_project):
        tc = _create_case(db, test_project.id, lifecycle_status="pending_review")
        result = transition(db, tc.id, "active")
        assert result.lifecycle_status == "active"

    def test_pending_review_to_active_auto_approve(self, db, test_project):
        tc = _create_case(db, test_project.id, lifecycle_status="pending_review")
        result = transition(db, tc.id, "active", auto_approve=True)
        assert result.lifecycle_status == "active"

    def test_pending_review_to_needs_modify(self, db, test_project):
        tc = _create_case(db, test_project.id, lifecycle_status="pending_review")
        result = transition(db, tc.id, "needs_modify", modification_hint="步骤3断言需更新")
        assert result.lifecycle_status == "needs_modify"

    def test_pending_review_to_deprecated(self, db, test_project):
        tc = _create_case(db, test_project.id, lifecycle_status="pending_review")
        result = transition(db, tc.id, "deprecated", reason="业务已下线")
        assert result.lifecycle_status == "deprecated"

    def test_active_to_needs_modify(self, db, test_project, test_user):
        tc = _create_case(db, test_project.id, lifecycle_status="active")
        review = _create_review(db, test_user.id)
        result = transition(db, tc.id, "needs_modify", review_id=review.id, modification_hint="需补充边界用例")
        assert result.lifecycle_status == "needs_modify"
        assert result.last_review_id == review.id

    def test_active_to_locator_broken(self, db, test_project):
        tc = _create_case(db, test_project.id, lifecycle_status="active")
        result = transition(db, tc.id, "locator_broken")
        assert result.lifecycle_status == "locator_broken"

    def test_active_to_deprecated(self, db, test_project, test_user):
        tc = _create_case(db, test_project.id, lifecycle_status="active")
        review = _create_review(db, test_user.id)
        result = transition(db, tc.id, "deprecated", reason="功能合并", review_id=review.id)
        assert result.lifecycle_status == "deprecated"
        assert result.last_review_id == review.id

    def test_needs_modify_to_pending_review_creates_new_version(self, db, test_project):
        tc = _create_case(db, test_project.id, lifecycle_status="needs_modify")
        result = transition(db, tc.id, "pending_review", modification_hint="修改步骤2")
        # 旧用例应变为 archived
        assert result.lifecycle_status == "archived"
        # 新用例应被创建，状态 pending_review，parent_case_id 指向旧用例
        new_case = db.query(TestCase).filter(
            TestCase.parent_case_id == tc.id,
            TestCase.lifecycle_status == "pending_review",
        ).first()
        assert new_case is not None
        assert new_case.parent_case_id == tc.id

    def test_locator_broken_to_active(self, db, test_project):
        tc = _create_case(db, test_project.id, lifecycle_status="locator_broken")
        result = transition(db, tc.id, "active")
        assert result.lifecycle_status == "active"

    def test_locator_broken_to_deprecated(self, db, test_project):
        tc = _create_case(db, test_project.id, lifecycle_status="locator_broken")
        result = transition(db, tc.id, "deprecated", reason="页面已移除")
        assert result.lifecycle_status == "deprecated"

    def test_deprecated_to_archived_after_cooldown(self, db, test_project):
        tc = _create_case(db, test_project.id, lifecycle_status="deprecated")
        # 模拟 deprecated 已超过冷却期：设置 deprecated_at 为 25 小时前
        enable_lifecycle_transition()
        try:
            tc.deprecated_at = datetime.now(timezone.utc) - timedelta(hours=25)
            db.flush()
            db.refresh(tc)
        finally:
            disable_lifecycle_transition()

        result = transition(db, tc.id, "archived")
        assert result.lifecycle_status == "archived"


# ==================== 非法迁移测试 ====================

class TestIllegalTransitions:
    """所有非法迁移应抛 IllegalStateTransition"""

    @pytest.mark.parametrize("from_s,to_s", [
        ("active", "draft"),
        ("active", "pending_review"),
        ("draft", "active"),
        ("draft", "archived"),
        ("archived", "active"),
        ("archived", "draft"),
        ("deprecated", "active"),
        ("deprecated", "needs_modify"),
        ("locator_broken", "pending_review"),
        ("needs_modify", "active"),
    ])
    def test_illegal_transition_raises(self, db, test_project, from_s, to_s):
        tc = _create_case(db, test_project.id, lifecycle_status=from_s)
        with pytest.raises(IllegalStateTransition) as exc_info:
            transition(db, tc.id, to_s)
        assert from_s in str(exc_info.value)
        assert to_s in str(exc_info.value)


# ==================== 前置条件校验测试 ====================

class TestPreconditionChecks:
    """迁移前置条件校验"""

    def test_active_to_needs_modify_without_review_id(self, db, test_project):
        """active → needs_modify 不带 review_id 抛错"""
        tc = _create_case(db, test_project.id, lifecycle_status="active")
        with pytest.raises(MissingReviewError):
            transition(db, tc.id, "needs_modify")

    def test_active_to_deprecated_without_reason(self, db, test_project, test_user):
        """active → deprecated 不带 deprecate_reason 抛错"""
        tc = _create_case(db, test_project.id, lifecycle_status="active")
        review = _create_review(db, test_user.id)
        with pytest.raises(MissingDeprecateReasonError):
            transition(db, tc.id, "deprecated", review_id=review.id)

    def test_active_to_deprecated_without_review_id(self, db, test_project):
        """active → deprecated 不带 review_id 抛错"""
        tc = _create_case(db, test_project.id, lifecycle_status="active")
        with pytest.raises(MissingReviewError):
            transition(db, tc.id, "deprecated", reason="废弃原因")

    def test_pending_review_to_deprecated_without_reason(self, db, test_project):
        """pending_review → deprecated 不带 reason 抛错"""
        tc = _create_case(db, test_project.id, lifecycle_status="pending_review")
        with pytest.raises(MissingDeprecateReasonError):
            transition(db, tc.id, "deprecated")

    def test_locator_broken_to_deprecated_without_reason(self, db, test_project):
        """locator_broken → deprecated 不带 reason 抛错"""
        tc = _create_case(db, test_project.id, lifecycle_status="locator_broken")
        with pytest.raises(MissingDeprecateReasonError):
            transition(db, tc.id, "deprecated")

    def test_deprecated_to_archived_within_cooldown(self, db, test_project):
        """deprecated → archived 24h 内拒绝"""
        tc = _create_case(db, test_project.id, lifecycle_status="deprecated")
        # updated_at 默认为当前时间，冷却期未满
        with pytest.raises(CooldownNotElapsedError) as exc_info:
            transition(db, tc.id, "archived")
        assert exc_info.value.remaining_hours > 0

    def test_deprecated_to_archived_no_timestamp_allows(self, db, test_project):
        """deprecated 用例无时间信息时允许归档（兼容旧数据）"""
        tc = _create_case(db, test_project.id, lifecycle_status="deprecated")
        # 用 patch 模拟 _check_cooldown 中 update_time=None, create_time=None 的场景
        with patch("app.services.lifecycle_service._check_cooldown"):
            result = transition(db, tc.id, "archived")
            assert result.lifecycle_status == "archived"


# ==================== Event Hook 测试 ====================

class TestLifecycleGuard:
    """测试直接修改 lifecycle_status 被 event hook 拦截"""

    def test_direct_update_lifecycle_status_raises(self, db, test_project):
        """直接 SQL UPDATE lifecycle_status 触发 RuntimeError"""
        tc = _create_case(db, test_project.id, lifecycle_status="active")
        tc.lifecycle_status = "deprecated"
        with pytest.raises(RuntimeError, match="Direct update of TestCase.lifecycle_status is forbidden"):
            db.flush()
        # flush 失败后从 session 移除脏对象，防止 teardown autoflush 再次触发 guard
        db.expunge(tc)

    def test_lifecycle_service_update_allowed(self, db, test_project):
        """通过 LifecycleService 更新 lifecycle_status 正常通过"""
        tc = _create_case(db, test_project.id, lifecycle_status="active")
        # transition 内部会 enable/disable guard
        result = transition(db, tc.id, "locator_broken")
        assert result.lifecycle_status == "locator_broken"

    def test_guard_enabled_allows_update(self, db, test_project):
        """手动 enable guard 后可以直接修改 lifecycle_status"""
        tc = _create_case(db, test_project.id, lifecycle_status="active")
        enable_lifecycle_transition()
        try:
            tc.lifecycle_status = "locator_broken"
            db.flush()
        finally:
            disable_lifecycle_transition()

        db.refresh(tc)
        assert tc.lifecycle_status == "locator_broken"


# ==================== 边界场景测试 ====================

class TestEdgeCases:
    """边界场景"""

    def test_transition_nonexistent_case(self, db, test_project):
        """不存在的 case_id 抛 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            transition(db, 999999, "active")

    def test_transition_with_review_id_recorded(self, db, test_project, test_user):
        """迁移时 review_id 被记录到 last_review_id"""
        tc = _create_case(db, test_project.id, lifecycle_status="active")
        review = _create_review(db, test_user.id)
        result = transition(db, tc.id, "needs_modify", review_id=review.id)
        assert result.last_review_id == review.id

    def test_pending_review_to_needs_modify_with_hint(self, db, test_project):
        """pending_review → needs_modify 记录 modification_hint"""
        tc = _create_case(db, test_project.id, lifecycle_status="pending_review")
        result = transition(db, tc.id, "needs_modify", modification_hint="断言值需更新")
        assert result.lifecycle_status == "needs_modify"

    def test_needs_modify_new_version_parent_case_id(self, db, test_project):
        """needs_modify → 新版本时 parent_case_id 正确指向旧用例"""
        tc = _create_case(db, test_project.id, lifecycle_status="needs_modify")
        transition(db, tc.id, "pending_review", modification_hint="修改步骤")

        new_case = db.query(TestCase).filter(
            TestCase.parent_case_id == tc.id,
        ).first()
        assert new_case is not None
        assert new_case.parent_case_id == tc.id
        assert new_case.lifecycle_status == "pending_review"
        # 旧用例应为 archived
        db.refresh(tc)
        assert tc.lifecycle_status == "archived"

    def test_needs_modify_multi_level_version_chain(self, db, test_project, test_user):
        """needs_modify 多次迭代时版本号递增且血缘链追溯正确"""
        # 第一轮：draft → pending_review → active → needs_modify
        tc1 = _create_case(db, test_project.id, lifecycle_status="draft")
        transition(db, tc1.id, "pending_review")
        transition(db, tc1.id, "active")
        review1 = _create_review(db, test_user.id)
        transition(db, tc1.id, "needs_modify", review_id=review1.id, modification_hint="第一轮修改")
        # needs_modify → pending_review，旧用例归档，新用例创建
        transition(db, tc1.id, "pending_review", modification_hint="提交修改")
        db.refresh(tc1)
        assert tc1.lifecycle_status == "archived"

        # 找到新版本（v2）
        tc2 = db.query(TestCase).filter(
            TestCase.parent_case_id == tc1.id,
            TestCase.lifecycle_status == "pending_review",
        ).first()
        assert tc2 is not None
        assert "-v2" in tc2.case_no

        # 第二轮：v2 → active → needs_modify → 新版本(v3)
        transition(db, tc2.id, "active")
        review2 = _create_review(db, test_user.id)
        transition(db, tc2.id, "needs_modify", review_id=review2.id, modification_hint="第二轮修改")
        transition(db, tc2.id, "pending_review", modification_hint="提交修改2")
        db.refresh(tc2)
        assert tc2.lifecycle_status == "archived"

        # 找到 v3
        tc3 = db.query(TestCase).filter(
            TestCase.parent_case_id == tc2.id,
            TestCase.lifecycle_status == "pending_review",
        ).first()
        assert tc3 is not None
        assert "-v3" in tc3.case_no

    def test_needs_modify_root_case_with_v_suffix(self, db, test_project, test_user):
        """根用例 case_no 已含 -v 后缀时，新版本号正确剥离后缀再递增"""
        # 创建一个 case_no 含 -v 后缀的根用例
        tc = _create_case(db, test_project.id, lifecycle_status="draft",
                          case_no="PROJ1-v1-special")
        transition(db, tc.id, "pending_review")
        transition(db, tc.id, "active")
        review = _create_review(db, test_user.id)
        transition(db, tc.id, "needs_modify", review_id=review.id, modification_hint="修改")
        transition(db, tc.id, "pending_review", modification_hint="提交")
        db.refresh(tc)
        assert tc.lifecycle_status == "archived"
        # 新用例的 case_no 应为 PROJ1-v2（剥离了 -v1 后缀再递增）
        new_case = db.query(TestCase).filter(
            TestCase.parent_case_id == tc.id,
            TestCase.lifecycle_status == "pending_review",
        ).first()
        assert new_case is not None
        assert new_case.case_no == "PROJ1-v2"

    def test_needs_modify_orphaned_parent_case_id(self, db, test_project, test_user):
        """parent_case_id 指向不存在的行时，while 循环 parent=None 触发 break，版本创建仍正常"""
        from sqlalchemy import text
        # 创建子用例，先正常插入
        tc = TestCase(
            project_id=test_project.id,
            case_no=f"ORPHAN-{datetime.now().strftime('%H%M%S%f')}",
            module="测试模块",
            title="孤儿用例测试",
            precondition="前置",
            steps_json=[],
            expected_result="预期",
            priority=1,
            case_type="UI",
            lifecycle_status="needs_modify",
        )
        enable_lifecycle_transition()
        try:
            db.add(tc)
            db.flush()
            db.refresh(tc)
            # 临时禁用 FK 检查，设置 parent_case_id 为不存在的值
            db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            db.execute(text("UPDATE test_cases SET parent_case_id = 999999 WHERE id = :id"), {"id": tc.id})
            db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.flush()
            db.expire(tc)  # 让 ORM 重新加载属性
        finally:
            disable_lifecycle_transition()

        # 此时 tc.parent_case_id=999999 指向不存在的行
        # transition → _create_new_version_case 中 while 循环查不到 parent，触发 break
        result = transition(db, tc.id, "pending_review", modification_hint="提交")
        db.refresh(tc)
        assert tc.lifecycle_status == "archived"
        new_case = db.query(TestCase).filter(
            TestCase.parent_case_id == tc.id,
            TestCase.lifecycle_status == "pending_review",
        ).first()
        assert new_case is not None

    def test_illegal_transition_with_detail(self):
        """IllegalStateTransition 支持 detail 参数"""
        exc = IllegalStateTransition("active", "draft", detail="archived is terminal")
        assert "active" in str(exc)
        assert "draft" in str(exc)
        assert "archived is terminal" in str(exc)

    def test_check_cooldown_none_timestamp(self, db, test_project):
        """_check_cooldown 在 deprecated_at=None 且 update_time=None 且 create_time=None 时允许归档"""
        from app.services.lifecycle_service import _check_cooldown
        tc = _create_case(db, test_project.id, lifecycle_status="deprecated")
        # 直接设置时间戳为 None 模拟旧数据
        enable_lifecycle_transition()
        try:
            tc.deprecated_at = None
            tc.update_time = None
            tc.create_time = None
            db.flush()
        finally:
            disable_lifecycle_transition()
        # _check_cooldown 不应抛异常
        _check_cooldown(tc)

    def test_check_cooldown_string_datetime(self, db, test_project):
        """_check_cooldown 兼容 MySQL 返回的字符串类型 datetime"""
        from app.services.lifecycle_service import _check_cooldown
        tc = _create_case(db, test_project.id, lifecycle_status="deprecated")
        # 设置 deprecated_at 为 25 小时前的字符串
        enable_lifecycle_transition()
        try:
            past_str = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
            tc.deprecated_at = past_str
            db.flush()
        finally:
            disable_lifecycle_transition()
        # _check_cooldown 不应抛异常（冷却期已过）
        _check_cooldown(tc)
