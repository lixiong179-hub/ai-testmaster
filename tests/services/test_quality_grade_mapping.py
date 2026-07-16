"""Task 17 quality_grade 后端持久化映射测试。

断言 grade_status_to_letter 正确将 4 档状态映射为 A/B/C/D 等级
（A=passed/B=warning/C=pending_review/D=rejected），
并通过 _save_test_case 集成测试验证入库后 quality_grade 与 gate_status 一致。

历史避坑：映射基于 grade_status（4档状态）而非 prior_quality_score（分数），
与 spec SubTask 17.3 对齐。
"""
from typing import Any, Dict, List, Tuple

import pytest

from app.core.config import settings
from app.models.test_case import TestCase as AppTestCase
from app.services.quality.grade import (
    GRADE_STATUS_TO_LETTER,
    grade_status_to_letter,
)
from app.services.test_case_generation.validator import CaseValidator as TestCaseGenerationValidateMixin


# ── grade_status_to_letter 单元测试 ──


class TestGradeStatusToLetter:
    """grade_status_to_letter 4 档状态到字母等级映射。"""

    def test_passed_to_a(self) -> None:
        assert grade_status_to_letter("passed") == "A"

    def test_warning_to_b(self) -> None:
        assert grade_status_to_letter("warning") == "B"

    def test_pending_review_to_c(self) -> None:
        assert grade_status_to_letter("pending_review") == "C"

    def test_rejected_to_d(self) -> None:
        assert grade_status_to_letter("rejected") == "D"

    def test_none_returns_none(self) -> None:
        assert grade_status_to_letter(None) is None

    def test_invalid_status_returns_none(self) -> None:
        assert grade_status_to_letter("invalid") is None

    def test_empty_string_returns_none(self) -> None:
        assert grade_status_to_letter("") is None


class TestGradeStatusToLetterConstant:
    """GRADE_STATUS_TO_LETTER 常量完整性。"""

    def test_constant_has_four_statuses(self) -> None:
        assert len(GRADE_STATUS_TO_LETTER) == 4

    def test_constant_mapping_correct(self) -> None:
        assert GRADE_STATUS_TO_LETTER == {
            "passed": "A",
            "warning": "B",
            "pending_review": "C",
            "rejected": "D",
        }

    def test_constant_values_are_valid_grades(self) -> None:
        from app.services.quality.grade import VALID_GRADES
        for letter in GRADE_STATUS_TO_LETTER.values():
            assert letter in VALID_GRADES


# ── _save_test_case 入库 quality_grade 集成测试 ──


class _DummyValidateService(TestCaseGenerationValidateMixin):
    """仅注入 db 的最小 Service 实现，供测试调用 _save_test_case。"""

    def __init__(self, db: Any) -> None:
        self.db = db


def _make_passed_case() -> Dict[str, Any]:
    """构造一条全维度通过的用例（gate_status=passed 时 quality_grade=A）。"""
    return {
        "title": "已登录用户打开绑定页面并完成保存校验全流程",
        "precondition": "账号已登录，浏览器网络正常，具备绑定页面访问权限",
        "steps": [
            {
                "step": "1",
                "description": "导航到绑定页面",
                "action": "导航到绑定页面",
                "action_type": "navigate",
                "expected_result": "绑定页面标题和主表单区域可见",
            },
            {
                "step": "2",
                "description": "点击保存按钮",
                "action": "点击保存按钮",
                "action_type": "click",
                "expected_result": "保存按钮保持可点击且页面显示保存完成提示",
            },
        ],
        "expected_result": "页面显示保存完成提示，绑定数据保存状态更新为已保存",
        "priority": 2,
        "case_type": "manual",
        "case_category": "positive",
    }


def _mock_gate_issues(status: str) -> Any:
    """构造 mock _quality_gate_issues classmethod，强制返回指定 status。

    返回 ([], status)：空 issues 列表确保不触发 AIGenerationError 阻断入库，
    让 _save_test_case 正常执行到 quality_grade 赋值与持久化。
    """
    def mock(cls: Any, *args: Any, **kwargs: Any) -> Tuple[List[str], str]:
        return [], status
    return classmethod(mock)  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_persisted_grade_passed(db, testProject, monkeypatch) -> None:
    """gate_status=passed 时入库 quality_grade=A。"""
    monkeypatch.setattr(settings, "AUTO_PARSE_PRECONDITION", False)
    monkeypatch.setattr(
        TestCaseGenerationValidateMixin,
        "_quality_gate_issues",
        _mock_gate_issues("passed"),
    )
    service = _DummyValidateService(db)
    saved = await service._save_test_case(
        project_id=testProject.id,
        generated_case=_make_passed_case(),
        test_point={"id": None, "module": "grade_mod", "priority": 2},
    )
    assert saved.quality_grade == "A"
    persisted = db.query(AppTestCase).filter(AppTestCase.id == saved.id).one()
    assert persisted.quality_grade == "A"


@pytest.mark.asyncio
async def test_persisted_grade_warning(db, testProject, monkeypatch) -> None:
    """gate_status=warning 时入库 quality_grade=B。"""
    monkeypatch.setattr(settings, "AUTO_PARSE_PRECONDITION", False)
    monkeypatch.setattr(
        TestCaseGenerationValidateMixin,
        "_quality_gate_issues",
        _mock_gate_issues("warning"),
    )
    service = _DummyValidateService(db)
    case = _make_passed_case()
    case["title"] = "已登录用户打开绑定页面并完成保存校验全流程_B"
    saved = await service._save_test_case(
        project_id=testProject.id,
        generated_case=case,
        test_point={"id": None, "module": "grade_mod", "priority": 2},
    )
    assert saved.quality_grade == "B"
    persisted = db.query(AppTestCase).filter(AppTestCase.id == saved.id).one()
    assert persisted.quality_grade == "B"


@pytest.mark.asyncio
async def test_persisted_grade_pending_review(db, testProject, monkeypatch) -> None:
    """gate_status=pending_review 时入库 quality_grade=C 且 lifecycle=pending_review。"""
    monkeypatch.setattr(settings, "AUTO_PARSE_PRECONDITION", False)
    monkeypatch.setattr(
        TestCaseGenerationValidateMixin,
        "_quality_gate_issues",
        _mock_gate_issues("pending_review"),
    )
    service = _DummyValidateService(db)
    case = _make_passed_case()
    case["title"] = "已登录用户打开绑定页面并完成保存校验全流程_C"
    saved = await service._save_test_case(
        project_id=testProject.id,
        generated_case=case,
        test_point={"id": None, "module": "grade_mod", "priority": 2},
    )
    assert saved.quality_grade == "C"
    assert saved.lifecycle_status == "pending_review"
    persisted = db.query(AppTestCase).filter(AppTestCase.id == saved.id).one()
    assert persisted.quality_grade == "C"


@pytest.mark.asyncio
async def test_persisted_grade_e2e_passed(db, testProject, monkeypatch) -> None:
    """端到端：全维度通过用例经真实 _quality_gate_issues 后 quality_grade=A。

    不 mock _quality_gate_issues，验证真实 QualityGateService + 本地硬性校验
    链路下，passed 用例的 quality_grade 正确持久化为 A。
    """
    monkeypatch.setattr(settings, "AUTO_PARSE_PRECONDITION", False)
    service = _DummyValidateService(db)
    saved = await service._save_test_case(
        project_id=testProject.id,
        generated_case=_make_passed_case(),
        test_point={"id": None, "module": "grade_mod_e2e", "priority": 2},
    )
    # 全维度通过用例应 passed → quality_grade=A
    assert saved.quality_grade == "A"
    persisted = db.query(AppTestCase).filter(AppTestCase.id == saved.id).one()
    assert persisted.quality_grade == "A"
