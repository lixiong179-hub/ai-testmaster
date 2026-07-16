"""CaseRefreshService 服务层测试（async 版本）。

覆盖范围:
    - create_suggestion: 创建保鲜建议（含 ai_result 字段映射、is_valid 处理）
    - build_refresh_prompt: 构造 AI 提示词（list/string/empty 步骤、None 字段兜底）
    - parse_refresh_response: 解析 AI 响应文本（plain json / 代码块 / 嵌入 json / 非法文本）
    - get_suggestion_by_id / get_case_by_id: 主键查询（存在 / 不存在）
    - list_suggestions: 分页 + 状态过滤 + dict 字段完整性
    - get_suggestions_stats: 状态聚合统计（空 / 混合 / 未知状态）
    - review_suggestion: 审核动作（approve 更新字段 / approve 废弃 / reject / 非法 action / 不存在 / 已审核）
    - scan_stale_cases: 过期用例扫描（空 / 无测试点 / 命中 / 已有 pending / 已删除 / 错误生命周期 / 需求未更新）
    - auto_scan_and_suggest: 空扫描路径（不触发 AI 调用）

使用真实 MySQL 测试库，依赖 tests/conftest.py 的 async_db fixture 提供事务隔离。
"""
import json
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.project import Project
from app.models.requirement import Requirement
from app.models.test_case import (
    TestCase,
    TestStep,
    enable_lifecycle_transition,
    disable_lifecycle_transition,
)
from app.models.test_point import TestPoint
from app.models.user import User
from app.services.case_refresh_service import CaseRefreshService
from app.utils.db_time import utcnow


# ==================== Fixtures ====================

@pytest_asyncio.fixture
async def cr_user(async_db):
    """创建测试用户，依赖 async_db fixture 事务回滚自动清理。"""
    user = User(
        username="cr_cov_user",
        email="cr_cov@test.com",
        password_hash="hash",
    )
    async_db.add(user)
    await async_db.flush()
    await async_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def cr_project(async_db, cr_user):
    """创建测试项目。"""
    project = Project(name="CR覆盖项目", user_id=cr_user.id)
    async_db.add(project)
    await async_db.flush()
    await async_db.refresh(project)
    return project


# ==================== 辅助构造函数 ====================

async def _make_case(db, project_id, **kwargs):
    """构造 TestCase，绕过 lifecycle guard 设置初始 lifecycle_status。"""
    case_no = kwargs.pop("case_no", f"CR-{utcnow().strftime('%H%M%S%f')}")
    case = TestCase(
        project_id=project_id,
        case_no=case_no,
        module=kwargs.get("module", "默认模块"),
        title=kwargs.get("title", "保鲜覆盖用例"),
        precondition=kwargs.get("precondition", "前置条件"),
        steps_json=kwargs.get("steps_json", [{"step": "步骤1", "action": "操作", "param": "参数"}]),
        expected_result=kwargs.get("expected_result", "预期结果"),
        priority=kwargs.get("priority", 1),
        case_type=kwargs.get("case_type", "UI"),
        lifecycle_status=kwargs.get("lifecycle_status", "active"),
        test_point_id=kwargs.get("test_point_id"),
        is_deleted=kwargs.get("is_deleted", False),
    )
    if "update_time" in kwargs:
        case.update_time = kwargs["update_time"]
    enable_lifecycle_transition()
    try:
        db.add(case)
        await db.flush()
        await db.refresh(case)
    finally:
        disable_lifecycle_transition()
    return case


async def _make_requirement(db, project_id, **kwargs):
    """构造 Requirement。"""
    req = Requirement(
        project_id=project_id,
        req_no=kwargs.pop("req_no", f"REQ-{utcnow().strftime('%H%M%S%f')}"),
        title=kwargs.get("title", "覆盖需求"),
        description=kwargs.get("description", "需求描述"),
        priority=kwargs.get("priority", 1),
        status=kwargs.get("status", "approved"),
    )
    if "update_time" in kwargs:
        req.update_time = kwargs["update_time"]
    db.add(req)
    await db.flush()
    await db.refresh(req)
    return req


async def _make_test_point(db, project_id, requirement_id, **kwargs):
    """构造 TestPoint。"""
    tp = TestPoint(
        project_id=project_id,
        requirement_id=requirement_id,
        module=kwargs.get("module", "默认模块"),
        point=kwargs.get("point", "测试点"),
        priority=kwargs.get("priority", 1),
    )
    db.add(tp)
    await db.flush()
    await db.refresh(tp)
    return tp


# ==================== create_suggestion ====================

class TestCreateSuggestion:

    async def test_create_minimal(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        assert sug.id is not None
        assert sug.case_id == case.id
        assert sug.trigger_reason == "manual"
        assert sug.suggestion_status == "pending"
        assert sug.review_status == "pending"
        assert sug.retry_count == 0
        assert sug.requirement_id is None
        assert sug.model_version is None

    async def test_create_with_requirement_and_model(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        req = await _make_requirement(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(
            case_id=case.id,
            trigger_reason="requirement_changed",
            requirement_id=req.id,
            model_version="gpt-4",
        )
        assert sug.requirement_id == req.id
        assert sug.model_version == "gpt-4"

    async def test_create_with_full_ai_result(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        ai_result = {
            "is_valid": True,
            "suggested_title": "新标题",
            "suggested_steps": [{"action": "点击", "expected_result": "成功"}],
            "suggested_expected_result": "新预期",
            "diff_description": "差异说明",
            "deprecation_reason": "",
        }
        sug = await svc.create_suggestion(
            case_id=case.id,
            trigger_reason="ai_scan",
            ai_result=ai_result,
        )
        assert sug.suggested_title == "新标题"
        assert sug.suggested_steps == [{"action": "点击", "expected_result": "成功"}]
        assert sug.suggested_expected_result == "新预期"
        assert sug.diff_description == "差异说明"
        assert sug.suggestion_status == "pending"

    async def test_create_with_invalid_ai_result_keeps_pending(self, async_db, cr_project):
        """ai_result is_valid=False 不改变 suggestion_status，仍为 pending。"""
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(
            case_id=case.id,
            trigger_reason="ai_scan",
            ai_result={"is_valid": False, "deprecation_reason": "用例已过时"},
        )
        assert sug.suggestion_status == "pending"
        assert sug.deprecation_reason == "用例已过时"

    async def test_create_without_ai_result_no_fields_set(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        assert sug.suggested_title is None
        assert sug.suggested_steps is None
        assert sug.suggested_expected_result is None
        assert sug.diff_description is None
        assert sug.deprecation_reason is None


# ==================== build_refresh_prompt ====================

class TestBuildRefreshPrompt:

    async def test_build_prompt_with_list_steps(self, async_db, cr_project):
        steps = [{"step": "1", "action": "点击"}]
        case = await _make_case(async_db, cr_project.id, steps_json=steps)
        req = await _make_requirement(async_db, cr_project.id, description="新版需求")
        svc = CaseRefreshService(async_db)
        prompt = svc.build_refresh_prompt(case, req)
        assert "新版需求" in prompt
        assert "保鲜覆盖用例" in prompt
        assert "预期结果" in prompt
        assert json.dumps(steps, ensure_ascii=False, indent=2) in prompt

    async def test_build_prompt_with_none_description(self, async_db, cr_project):
        """requirement.description 为 None 时用空字符串兜底。

        仅在内存置 None 验证 pure function 兜底逻辑，不 flush 落库
        （DB 列 description NOT NULL，落库会触发 IntegrityError）。
        """
        case = await _make_case(async_db, cr_project.id)
        req = await _make_requirement(async_db, cr_project.id)
        req.description = None
        svc = CaseRefreshService(async_db)
        prompt = svc.build_refresh_prompt(case, req)
        assert "最新需求" in prompt

    async def test_build_prompt_with_string_steps(self, async_db, cr_project):
        """steps_json 为非 list 类型时走 str() 分支。"""
        case = await _make_case(async_db, cr_project.id)
        case.steps_json = "步骤文本而非列表"
        await async_db.flush()
        req = await _make_requirement(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        prompt = svc.build_refresh_prompt(case, req)
        assert "步骤文本而非列表" in prompt

    async def test_build_prompt_with_empty_steps(self, async_db, cr_project):
        """steps_json 为空列表（falsy）时 steps_text 保持空字符串。"""
        case = await _make_case(async_db, cr_project.id, steps_json=[])
        req = await _make_requirement(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        prompt = svc.build_refresh_prompt(case, req)
        assert "标题：" in prompt
        assert "预期结果：" in prompt


# ==================== parse_refresh_response ====================

class TestParseRefreshResponse:

    async def test_parse_plain_json(self, async_db):
        svc = CaseRefreshService(async_db)
        text = json.dumps({"is_valid": True, "suggested_title": "标题"}, ensure_ascii=False)
        result = svc.parse_refresh_response(text)
        assert result["is_valid"] is True
        assert result["suggested_title"] == "标题"

    async def test_parse_code_block_json(self, async_db):
        svc = CaseRefreshService(async_db)
        text = '```json\n{"is_valid": false, "deprecation_reason": "过时"}\n```'
        result = svc.parse_refresh_response(text)
        assert result["is_valid"] is False
        assert result["deprecation_reason"] == "过时"

    async def test_parse_code_block_without_lang(self, async_db):
        svc = CaseRefreshService(async_db)
        text = '```\n{"is_valid": true}\n```'
        result = svc.parse_refresh_response(text)
        assert result["is_valid"] is True

    async def test_parse_embedded_json(self, async_db):
        """JSON 嵌入在非 JSON 文本中，正则提取大括号块。"""
        svc = CaseRefreshService(async_db)
        text = 'AI响应: {"is_valid": true, "diff_description": "差异"} 完成'
        result = svc.parse_refresh_response(text)
        assert result["is_valid"] is True
        assert result["diff_description"] == "差异"

    async def test_parse_invalid_returns_default(self, async_db):
        svc = CaseRefreshService(async_db)
        result = svc.parse_refresh_response("这不是JSON")
        assert result == {"is_valid": True, "diff_description": "AI响应解析失败，需人工判断"}

    async def test_parse_empty_string(self, async_db):
        svc = CaseRefreshService(async_db)
        result = svc.parse_refresh_response("")
        assert result["is_valid"] is True
        assert "解析失败" in result["diff_description"]


# ==================== get_suggestion_by_id / get_case_by_id ====================

class TestGetById:

    async def test_get_suggestion_existing(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        created = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        found = await svc.get_suggestion_by_id(created.id)
        assert found is not None
        assert found.id == created.id

    async def test_get_suggestion_nonexistent(self, async_db):
        svc = CaseRefreshService(async_db)
        assert await svc.get_suggestion_by_id(99999999) is None

    async def test_get_case_existing(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        found = await svc.get_case_by_id(case.id)
        assert found is not None
        assert found.id == case.id

    async def test_get_case_nonexistent(self, async_db):
        svc = CaseRefreshService(async_db)
        assert await svc.get_case_by_id(99999999) is None


# ==================== list_suggestions ====================

class TestListSuggestions:

    async def test_list_empty(self, async_db, cr_project):
        svc = CaseRefreshService(async_db)
        result = await svc.list_suggestions(cr_project.id)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["page"] == 1
        assert result["page_size"] == 20

    async def test_list_with_data(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        for _ in range(3):
            await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        result = await svc.list_suggestions(cr_project.id)
        assert result["total"] == 3
        assert len(result["items"]) == 3

    async def test_list_pagination(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        for _ in range(5):
            await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        page1 = await svc.list_suggestions(cr_project.id, page=1, page_size=2)
        page2 = await svc.list_suggestions(cr_project.id, page=2, page_size=2)
        assert page1["total"] == 5
        assert len(page1["items"]) == 2
        assert len(page2["items"]) == 2
        page1_ids = {item["id"] for item in page1["items"]}
        page2_ids = {item["id"] for item in page2["items"]}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_list_filter_suggestion_status(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        s1 = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        s2 = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        s2.suggestion_status = "applied"
        await async_db.flush()
        result = await svc.list_suggestions(cr_project.id, suggestion_status="pending")
        assert result["total"] == 1
        assert result["items"][0]["id"] == s1.id

    async def test_list_filter_review_status(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        s1 = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        s2 = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        s2.review_status = "approved"
        await async_db.flush()
        result = await svc.list_suggestions(cr_project.id, review_status="pending")
        assert result["total"] == 1
        assert result["items"][0]["id"] == s1.id

    async def test_list_dict_contains_all_fields(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(
            case_id=case.id,
            trigger_reason="manual",
            ai_result={"suggested_title": "新标题", "diff_description": "差异"},
            model_version="gpt-4",
        )
        result = await svc.list_suggestions(cr_project.id)
        item = result["items"][0]
        assert item["id"] == sug.id
        assert item["case_id"] == case.id
        assert item["trigger_reason"] == "manual"
        assert item["suggestion_status"] == "pending"
        assert item["review_status"] == "pending"
        assert item["suggested_title"] == "新标题"
        assert item["diff_description"] == "差异"
        assert item["model_version"] == "gpt-4"
        assert item["triggered_at"] is not None


# ==================== get_suggestions_stats ====================

class TestGetSuggestionsStats:

    async def test_stats_empty(self, async_db, cr_project):
        svc = CaseRefreshService(async_db)
        stats = await svc.get_suggestions_stats(cr_project.id)
        assert stats == {"pending": 0, "applied": 0, "rejected": 0, "total": 0}

    async def test_stats_with_mixed_statuses(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        s1 = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        s2 = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        s3 = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        s2.suggestion_status = "applied"
        s3.suggestion_status = "rejected"
        await async_db.flush()
        stats = await svc.get_suggestions_stats(cr_project.id)
        assert stats["pending"] == 1
        assert stats["applied"] == 1
        assert stats["rejected"] == 1
        assert stats["total"] == 3

    async def test_stats_with_unknown_status_only_counted_in_total(self, async_db, cr_project):
        """未知状态不计入 pending/applied/rejected，但 total 仍累加。"""
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        s = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        s.suggestion_status = "expired"
        await async_db.flush()
        stats = await svc.get_suggestions_stats(cr_project.id)
        assert stats["pending"] == 0
        assert stats["applied"] == 0
        assert stats["rejected"] == 0
        assert stats["total"] == 1


# ==================== review_suggestion ====================

class TestReviewSuggestion:

    async def test_review_reject(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        result = await svc.review_suggestion(
            suggestion_id=sug.id,
            action="reject",
            reviewer_id=1,
            reviewer_name="reviewer",
            reject_reason="建议无效",
        )
        assert result.review_status == "rejected"
        assert result.suggestion_status == "rejected"
        assert result.reviewer_id == 1
        assert result.reviewer_name == "reviewer"
        assert result.reviewed_at is not None
        assert result.reject_reason == "建议无效"

    async def test_review_reject_without_reason(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        result = await svc.review_suggestion(
            suggestion_id=sug.id,
            action="reject",
            reviewer_id=1,
            reviewer_name="reviewer",
        )
        assert result.review_status == "rejected"
        assert result.reject_reason == ""

    async def test_review_approve_updates_case_fields(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id, lifecycle_status="active")
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(
            case_id=case.id,
            trigger_reason="ai_scan",
            ai_result={
                "is_valid": True,
                "suggested_title": "更新后的标题",
                "suggested_steps": [
                    {"action": "点击按钮", "expected_result": "弹出对话框", "action_type": "click"}
                ],
                "suggested_expected_result": "更新后的预期",
                "diff_description": "差异说明",
            },
        )
        result = await svc.review_suggestion(
            suggestion_id=sug.id,
            action="approve",
            reviewer_id=1,
            reviewer_name="reviewer",
        )
        assert result.review_status == "approved"
        assert result.suggestion_status == "applied"
        assert result.snapshot_version_id > 0
        await async_db.refresh(case)
        assert case.title == "更新后的标题"
        assert case.expected_result == "更新后的预期"
        steps = (
            (
                await async_db.execute(
                    select(TestStep)
                    .where(TestStep.test_case_id == case.id)
                    .order_by(TestStep.step_number)
                )
            )
            .scalars()
            .all()
        )
        assert len(steps) == 1
        assert steps[0].action == "点击按钮"
        assert steps[0].expected_result == "弹出对话框"
        assert steps[0].action_type == "click"

    async def test_review_approve_deprecation(self, async_db, cr_project, cr_user):
        """approve + deprecation_reason 走 lifecycle 废弃分支。"""
        case = await _make_case(async_db, cr_project.id, lifecycle_status="active")
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(
            case_id=case.id,
            trigger_reason="ai_scan",
            ai_result={
                "is_valid": False,
                "deprecation_reason": "用例已过时",
            },
        )
        result = await svc.review_suggestion(
            suggestion_id=sug.id,
            action="approve",
            reviewer_id=cr_user.id,
            reviewer_name="reviewer",
        )
        assert result.review_status == "approved"
        assert result.suggestion_status == "applied"
        # lifecycle_transition 内部 flush 会令原实例脱离 persistent 状态，需重新查询
        refreshed = (
            await async_db.execute(
                select(TestCase).where(TestCase.id == case.id)
            )
        ).scalar_one_or_none()
        assert refreshed.lifecycle_status == "deprecated"
        assert refreshed.deprecated_at is not None

    async def test_review_invalid_action(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        with pytest.raises(ValueError, match="无效的审核操作"):
            await svc.review_suggestion(
                suggestion_id=sug.id,
                action="invalid",
                reviewer_id=1,
                reviewer_name="reviewer",
            )

    async def test_review_nonexistent(self, async_db):
        svc = CaseRefreshService(async_db)
        with pytest.raises(ValueError, match="保鲜建议不存在"):
            await svc.review_suggestion(
                suggestion_id=99999999,
                action="reject",
                reviewer_id=1,
                reviewer_name="reviewer",
            )

    async def test_review_already_reviewed(self, async_db, cr_project):
        case = await _make_case(async_db, cr_project.id)
        svc = CaseRefreshService(async_db)
        sug = await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        await svc.review_suggestion(
            suggestion_id=sug.id,
            action="reject",
            reviewer_id=1,
            reviewer_name="reviewer",
        )
        with pytest.raises(ValueError, match="保鲜建议已审核"):
            await svc.review_suggestion(
                suggestion_id=sug.id,
                action="reject",
                reviewer_id=2,
                reviewer_name="reviewer2",
            )


# ==================== scan_stale_cases ====================

class TestScanStaleCases:

    async def test_scan_empty_project(self, async_db, cr_project):
        svc = CaseRefreshService(async_db)
        assert await svc.scan_stale_cases(cr_project.id) == []

    async def test_scan_case_without_test_point_skipped(self, async_db, cr_project):
        await _make_case(async_db, cr_project.id, lifecycle_status="active")
        svc = CaseRefreshService(async_db)
        assert await svc.scan_stale_cases(cr_project.id) == []

    async def test_scan_stale_case_detected(self, async_db, cr_project):
        now = utcnow()
        past = now - timedelta(days=2)
        req = await _make_requirement(async_db, cr_project.id, update_time=now)
        tp = await _make_test_point(async_db, cr_project.id, req.id)
        case = await _make_case(
            async_db,
            cr_project.id,
            lifecycle_status="active",
            test_point_id=tp.id,
            update_time=past,
        )
        svc = CaseRefreshService(async_db)
        result = await svc.scan_stale_cases(cr_project.id)
        assert len(result) == 1
        assert result[0]["case_id"] == case.id
        assert result[0]["requirement_id"] == req.id
        assert result[0]["trigger_reason"] == "requirement_changed"

    async def test_scan_skips_existing_pending_suggestion(self, async_db, cr_project):
        now = utcnow()
        past = now - timedelta(days=2)
        req = await _make_requirement(async_db, cr_project.id, update_time=now)
        tp = await _make_test_point(async_db, cr_project.id, req.id)
        case = await _make_case(
            async_db,
            cr_project.id,
            lifecycle_status="active",
            test_point_id=tp.id,
            update_time=past,
        )
        svc = CaseRefreshService(async_db)
        await svc.create_suggestion(case_id=case.id, trigger_reason="manual")
        assert await svc.scan_stale_cases(cr_project.id) == []

    async def test_scan_skips_deleted_case(self, async_db, cr_project):
        now = utcnow()
        past = now - timedelta(days=2)
        req = await _make_requirement(async_db, cr_project.id, update_time=now)
        tp = await _make_test_point(async_db, cr_project.id, req.id)
        await _make_case(
            async_db,
            cr_project.id,
            lifecycle_status="active",
            test_point_id=tp.id,
            update_time=past,
            is_deleted=True,
        )
        svc = CaseRefreshService(async_db)
        assert await svc.scan_stale_cases(cr_project.id) == []

    async def test_scan_skips_wrong_lifecycle(self, async_db, cr_project):
        now = utcnow()
        past = now - timedelta(days=2)
        req = await _make_requirement(async_db, cr_project.id, update_time=now)
        tp = await _make_test_point(async_db, cr_project.id, req.id)
        await _make_case(
            async_db,
            cr_project.id,
            lifecycle_status="deprecated",
            test_point_id=tp.id,
            update_time=past,
        )
        svc = CaseRefreshService(async_db)
        assert await svc.scan_stale_cases(cr_project.id) == []

    async def test_scan_skips_when_requirement_not_updated(self, async_db, cr_project):
        """req.update_time <= case.update_time 时不判定为 stale。"""
        now = utcnow()
        older = now - timedelta(days=2)
        req = await _make_requirement(async_db, cr_project.id, update_time=older)
        tp = await _make_test_point(async_db, cr_project.id, req.id)
        await _make_case(
            async_db,
            cr_project.id,
            lifecycle_status="active",
            test_point_id=tp.id,
            update_time=now,
        )
        svc = CaseRefreshService(async_db)
        assert await svc.scan_stale_cases(cr_project.id) == []


# ==================== auto_scan_and_suggest（空扫描路径） ====================

class TestAutoScanAndSuggest:

    async def test_auto_scan_no_stale_returns_empty(self, async_db, cr_project):
        """无 stale 用例时不触发 AI 调用，返回空 created 列表。"""
        svc = CaseRefreshService(async_db)
        result = await svc.auto_scan_and_suggest(cr_project.id, max_cases=5)
        assert result["created"] == []
        assert result["errors"] == []
        assert result["total_scanned"] == 0

    async def test_auto_scan_max_cases_param(self, async_db, cr_project):
        svc = CaseRefreshService(async_db)
        result = await svc.auto_scan_and_suggest(cr_project.id, max_cases=1)
        assert result["total_scanned"] == 0
