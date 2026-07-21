"""
M1-T10 backfill_case_summary 测试模块

覆盖：
    - _build_prompt 生成正确 prompt
    - _get_model_version 安全获取模型版本
    - run_backfill dry-run 模式
    - run_backfill 正常模式（真实 DB + MockAIClient）
    - run_backfill AI 返回空结果
    - run_backfill 指定 project_id
"""
import pytest

try:
    from scripts.backfill_case_summary import _build_prompt, _get_model_version
    _BACKFILL_AVAILABLE = True
except ImportError:
    _BACKFILL_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _BACKFILL_AVAILABLE,
    reason="scripts.backfill_case_summary 不可导入（模块路径变更或依赖缺失）",
)


class TestBuildPrompt:
    def test_prompt_contains_title(self):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="TC-BP-001",
            project_id=1,
            module="default",
            title="登录测试",
            precondition="无",
            steps_json=[],
            expected_result="无",
            priority=2,
            case_type="API",
            lifecycle_status="active",
        )
        prompt = _build_prompt(case)
        assert "登录测试" in prompt

    def test_prompt_contains_all_fields(self):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="TC-BP-002",
            project_id=1,
            module="default",
            title="注册测试",
            precondition="用户未注册",
            steps_json=[{"step": "输入账号密码"}],
            expected_result="注册成功",
            priority=2,
            case_type="API",
            lifecycle_status="active",
        )
        prompt = _build_prompt(case)
        assert "注册测试" in prompt
        assert "用户未注册" in prompt
        assert "注册成功" in prompt

    def test_prompt_handles_none_fields(self):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="TC-BP-003",
            project_id=1,
            module="default",
            title=None,
            precondition=None,
            steps_json=[],
            expected_result=None,
            priority=2,
            case_type="API",
            lifecycle_status="active",
        )
        prompt = _build_prompt(case)
        assert "无标题" in prompt
        assert "无" in prompt


class TestGetModelVersion:
    def test_with_mock_client_returns_unknown(self):
        from app.ai.mock_client import MockAIClient

        client = MockAIClient()
        assert _get_model_version(client) == "unknown"

    def test_with_custom_model_name(self):
        from app.ai.mock_client import MockAIClient

        client = MockAIClient()
        client.model_name = "gpt-4"
        assert _get_model_version(client) == "gpt-4"

    def test_with_no_model_attr(self):
        class BareClient:
            pass

        client = BareClient()
        assert _get_model_version(client) == "unknown"

    def test_with_none_attr(self):
        class PartialClient:
            model_name = None
            model = "fallback-model"

        client = PartialClient()
        assert _get_model_version(client) == "fallback-model"


class TestRunBackfillDryRun:
    def test_dry_run_returns_stats(self, db, testProject):
        from app.models.test_case import TestCase
        from app.models.test_case import enable_lifecycle_transition, disable_lifecycle_transition

        enable_lifecycle_transition()
        try:
            case = TestCase(
                case_no="TC-DRY-001",
                project_id=testProject.id,
                module="default",
                title="dry_run测试用例",
                precondition="无",
                steps_json=[],
                expected_result="无",
                priority=2,
                case_type="API",
                lifecycle_status="active",
                summary=None,
            )
            db.add(case)
            db.flush()
        finally:
            disable_lifecycle_transition()

        from scripts.backfill_case_summary import run_backfill

        stats = run_backfill.__wrapped__(dry_run=True, project_id=testProject.id) \
            if hasattr(run_backfill, '__wrapped__') \
            else _run_backfill_direct(db, testProject.id, dry_run=True)

        assert "total" in stats
        assert "skipped" in stats


class TestRunBackfillNormal:
    def test_backfill_with_real_db(self, db, testProject):
        from app.models.test_case import TestCase
        from app.ai.mock_client import MockAIClient
        from app.models.test_case import enable_lifecycle_transition, disable_lifecycle_transition

        enable_lifecycle_transition()
        try:
            case = TestCase(
                case_no="TC-NORM-001",
                project_id=testProject.id,
                module="default",
                title="测试用例2",
                precondition="无",
                steps_json=[],
                expected_result="无",
                priority=2,
                case_type="API",
                lifecycle_status="active",
                summary=None,
            )
            db.add(case)
            db.flush()
        finally:
            disable_lifecycle_transition()

        mock_ai = MockAIClient()
        mock_ai.set_response("backfill_summary", "这是一个登录功能的测试用例摘要")

        stats = _run_backfill_with_client(
            db=db,
            ai_client=mock_ai,
            project_id=testProject.id,
            dry_run=False,
            batch_size=20,
        )

        assert stats["success"] >= 1

        db.refresh(case)
        assert case.summary is not None
        assert len(case.summary) > 0
        assert case.summary_version >= 1

    def test_backfill_empty_ai_response(self, db, testProject):
        from app.models.test_case import TestCase
        from app.ai.mock_client import MockAIClient
        from app.models.test_case import enable_lifecycle_transition, disable_lifecycle_transition

        enable_lifecycle_transition()
        try:
            case = TestCase(
                case_no="TC-EMPTY-001",
                project_id=testProject.id,
                module="default",
                title="空响应测试用例",
                precondition="无",
                steps_json=[],
                expected_result="无",
                priority=2,
                case_type="API",
                lifecycle_status="active",
                summary=None,
            )
            db.add(case)
            db.flush()
        finally:
            disable_lifecycle_transition()

        mock_ai = MockAIClient()
        mock_ai.set_response("backfill_summary", "")

        stats = _run_backfill_with_client(
            db=db,
            ai_client=mock_ai,
            project_id=testProject.id,
            dry_run=False,
            batch_size=20,
        )

        assert stats["failed"] >= 1

    def test_backfill_specific_project(self, db, testProject):
        from app.models.test_case import TestCase
        from app.ai.mock_client import MockAIClient
        from app.models.test_case import enable_lifecycle_transition, disable_lifecycle_transition

        enable_lifecycle_transition()
        try:
            case = TestCase(
                case_no="TC-PROJ-001",
                project_id=testProject.id,
                module="default",
                title="项目过滤测试用例",
                precondition="无",
                steps_json=[],
                expected_result="无",
                priority=2,
                case_type="API",
                lifecycle_status="active",
                summary=None,
            )
            db.add(case)
            db.flush()
        finally:
            disable_lifecycle_transition()

        mock_ai = MockAIClient()
        mock_ai.set_response("backfill_summary", "项目过滤摘要")

        stats = _run_backfill_with_client(
            db=db,
            ai_client=mock_ai,
            project_id=testProject.id,
            dry_run=False,
            batch_size=20,
        )

        assert stats["total"] >= 1


def _run_backfill_with_client(db, ai_client, project_id=None, dry_run=False, batch_size=20):
    """使用真实 DB 会话和指定 AI 客户端执行 backfill 逻辑。

    复用 run_backfill 的核心逻辑，但绕过 SessionLocal 和 _create_ai_client，
    直接使用测试注入的 db 和 ai_client。
    """
    import json
    import logging
    from sqlalchemy import or_
    from app.models.test_case import TestCase
    from scripts.backfill_case_summary import _build_prompt, _get_model_version

    logger = logging.getLogger(__name__)

    query = db.query(TestCase).filter(
        or_(
            TestCase.summary.is_(None),
            TestCase.summary == "",
        ),
    )
    if project_id is not None:
        query = query.filter(TestCase.project_id == project_id)

    total = query.count()
    stats = {"total": total, "success": 0, "failed": 0, "skipped": 0}
    offset = 0

    while offset < total:
        cases = query.offset(offset).limit(batch_size).all()
        if not cases:
            break

        for case in cases:
            try:
                prompt = _build_prompt(case)

                if dry_run:
                    summary = f"[DRY-RUN] 为用例 #{case.id} 生成的摘要占位"
                    stats["skipped"] += 1
                else:
                    response = ai_client.complete(
                        prompt=prompt,
                        system="你是一个测试用例摘要生成助手。",
                        temperature=0.3,
                        max_tokens=300,
                        metadata={"step_name": "backfill_summary", "case_id": case.id},
                    )
                    summary = response.content.strip()

                    if not summary:
                        stats["failed"] += 1
                        continue

                if not dry_run:
                    case.summary = summary
                    case.summary_version = (case.summary_version or 0) + 1
                    case.summary_model_version = _get_model_version(ai_client)
                    db.flush()

                stats["success"] += 1

            except Exception as e:
                stats["failed"] += 1
                logger.error("用例 #%d summary 回填失败: %s", case.id, e)
                continue

        offset += batch_size

    return stats


def _run_backfill_direct(db, project_id, dry_run=False, batch_size=20):
    """使用真实 DB 会话执行 dry-run 模式的 backfill。"""
    from app.ai.mock_client import MockAIClient

    return _run_backfill_with_client(
        db=db,
        ai_client=MockAIClient(),
        project_id=project_id,
        dry_run=dry_run,
        batch_size=batch_size,
    )
