"""M3-T01 ReverseInfer Step 单元测试

覆盖：
    - should_run / cache_key / validate_output / fallback
    - execute 新项目模式（仅有 UI，无历史指纹）
    - execute 旧项目模式（UI + 历史指纹）
    - execute 缺少 raw_signals / project_id / UI
    - AI 返回解析：有效 JSON / 无效 JSON / 数组回退
    - pause_for_confirmation 低置信度触发
    - _parse_infer_response / _validate_new_project_output / _validate_old_project_output
    - _build_ui_text / _build_fingerprint_text
    - _hash_dict / _clamp_float
    - 新项目校验：缺 overall_confidence / 缺 capability 字段 / 非数组
    - 旧项目校验：缺 change_summary / change_summary 非对象 / 子字段非数组

使用真实 MySQL 数据库 + MockAIClient。
"""
import json
import pytest

from app.ai.mock_client import MockAIClient
from app.models.iteration import Iteration
from app.models.pipeline import Artifact
from app.pipelines.steps.reverse_infer import (
    ReverseInfer,
    _build_ui_text,
    _build_fingerprint_text,
    _parse_infer_response,
    _validate_new_project_output,
    _validate_old_project_output,
    _hash_dict,
    _clamp_float,
)
from app.services import pipeline_service
from app.pipelines.context import PipelineContext


def _make_raw_signals(project_id: int, **overrides) -> dict:
    payload = {
        "iteration_id": 1,
        "project_id": project_id,
        "prd_content": "",
        "ui_descriptions": [
            {
                "screen_id": 1,
                "screen_name": "登录页",
                "description": "用户输入账号密码登录",
            },
            {
                "screen_id": 2,
                "screen_name": "注册页",
                "description": "新用户填写信息注册",
            },
        ],
        "ui_specs": [
            {
                "screen_id": 1,
                "screen_name": "登录页",
                "ui_spec": {
                    "components": [
                        {"type": "input", "name": "username"},
                        {"type": "input", "name": "password"},
                        {"type": "button", "name": "login_btn"},
                    ]
                },
            },
            {
                "screen_id": 2,
                "screen_name": "注册页",
                "ui_spec": {
                    "components": [
                        {"type": "input", "name": "email"},
                        {"type": "input", "name": "nickname"},
                        {"type": "button", "name": "register_btn"},
                    ]
                },
            },
        ],
        "test_points": [],
        "has_ui": True,
        "has_prd": False,
        "has_testpoints": False,
    }
    payload.update(overrides)
    return payload


def _make_fingerprints(project_id: int) -> dict:
    fps = []
    for i, mod_info in enumerate([("用户管理", "user_mgmt"), ("订单管理", "order_mgmt")]):
        fps.append({
            "case_id": 200 + i,
            "title": f"旧用例{i}",
            "module": mod_info[0],
            "summary": f"旧用例摘要{i}",
            "priority": 1,
            "lifecycle_status": "active",
        })
    return {
        "project_id": project_id,
        "fingerprints": fps,
        "total_count": len(fps),
        "stale_backfilled_count": 0,
    }


@pytest.fixture
def mock_ai():
    return MockAIClient()


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="reverse_infer_test_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


@pytest.fixture
def make_ctx(db, mock_ai, test_iteration):
    def _make_ctx(raw_signals_payload=None, fingerprints_payload=None):
        run = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash="reverse_infer_test_hash",
            pipeline_version="1.0",
        )
        db.flush()

        ctx = PipelineContext(
            db=db,
            ai_client=mock_ai,
            run=run,
            iteration_id=test_iteration.id,
            user_id=1,
        )

        if raw_signals_payload is not None:
            artifact = Artifact(
                run_id=run.id,
                kind="raw_signals",
                schema_version="1.0",
                payload=raw_signals_payload,
                content_hash="sig_hash",
            )
            db.add(artifact)
            db.flush()
            ctx.set_artifact("raw_signals", artifact)

        if fingerprints_payload is not None:
            artifact = Artifact(
                run_id=run.id,
                kind="history_fingerprints",
                schema_version="1.0",
                payload=fingerprints_payload,
                content_hash="fp_hash",
            )
            db.add(artifact)
            db.flush()
            ctx.set_artifact("history_fingerprints", artifact)

        return ctx
    return _make_ctx


# ==================== 类级方法测试 ====================

class TestShouldRun:
    def test_has_ui(self, make_ctx):
        step = ReverseInfer()
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(1, has_ui=True))
        assert step.should_run(ctx) is True

    def test_no_ui(self, make_ctx):
        step = ReverseInfer()
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(1, has_ui=False))
        assert step.should_run(ctx) is False

    def test_no_signals(self, make_ctx):
        step = ReverseInfer()
        ctx = make_ctx()
        assert step.should_run(ctx) is False


class TestCacheKey:
    def test_has_ui_and_fingerprints(self, make_ctx):
        step = ReverseInfer()
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(1),
            fingerprints_payload=_make_fingerprints(1),
        )
        key = step.cache_key(ctx)
        assert key and len(key) == 64

    def test_has_ui_only(self, make_ctx):
        step = ReverseInfer()
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(1))
        key = step.cache_key(ctx)
        assert key and len(key) == 64

    def test_no_signals(self, make_ctx):
        step = ReverseInfer()
        ctx = make_ctx()
        assert step.cache_key(ctx) == ""


class TestValidateOutput:
    def test_valid(self):
        step = ReverseInfer()
        payload = {
            "iteration_id": 1,
            "project_id": 1,
            "parsed": {"overall_confidence": 0.8},
        }
        assert step.validate_output(payload) is True

    def test_missing_iteration_id(self):
        step = ReverseInfer()
        payload = {"project_id": 1, "parsed": {"overall_confidence": 0.8}}
        assert step.validate_output(payload) is False

    def test_missing_overall_confidence(self):
        step = ReverseInfer()
        payload = {
            "iteration_id": 1,
            "project_id": 1,
            "parsed": {"other": "data"},
        }
        assert step.validate_output(payload) is False

    def test_parsed_not_dict(self):
        step = ReverseInfer()
        payload = {
            "iteration_id": 1,
            "project_id": 1,
            "parsed": "not a dict",
        }
        assert step.validate_output(payload) is False


class TestFallback:
    def test_returns_degraded(self, make_ctx):
        step = ReverseInfer()
        ctx = make_ctx()
        result = step.fallback(ctx, Exception("test"))
        assert result.success is False
        assert result.degraded is True
        assert "业务反推失败" in (result.error or "")


# ==================== execute 测试 ====================

class TestExecuteNewProject:
    def test_success(self, make_ctx, mock_ai):
        mock_ai.set_response("reverse_infer", {
            "inferred_capabilities": [
                {
                    "name": "用户认证",
                    "key": "user_auth",
                    "description": "用户通过账号密码登录系统",
                    "confidence": 0.9,
                    "supporting_evidence": "登录页有username/password输入框和登录按钮",
                },
                {
                    "name": "用户注册",
                    "key": "user_registration",
                    "description": "新用户填写邮箱和昵称注册",
                    "confidence": 0.85,
                    "supporting_evidence": "注册页有email/nickname输入框和注册按钮",
                },
            ],
            "uncertain_questions": [
                {
                    "question": "登录失败是否有锁定机制？",
                    "context": "登录页",
                    "suggested_answer": "通常3次失败后锁定30分钟",
                }
            ],
            "overall_confidence": 0.85,
            "analysis_summary": "系统包含用户认证和注册两大核心能力",
        })
        step = ReverseInfer()
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(1))
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "inferred_business_summary"
        assert result.artifact_payload is not None
        assert result.artifact_payload["mode"] == "new_project"
        assert result.artifact_payload["confidence"] == 0.85
        assert result.artifact_payload["uncertain_question_count"] == 1
        assert result.pause_for_confirmation is False

    def test_only_ui_specs_no_descriptions(self, make_ctx, mock_ai):
        mock_ai.set_response("reverse_infer", {
            "inferred_capabilities": [
                {
                    "name": "用户认证",
                    "key": "user_auth",
                    "description": "用户通过账号密码登录",
                    "confidence": 0.9,
                    "supporting_evidence": "登录页控件",
                }
            ],
            "uncertain_questions": [],
            "overall_confidence": 0.9,
            "analysis_summary": "包含用户认证能力",
        })
        signals = _make_raw_signals(1)
        signals["ui_descriptions"] = []
        step = ReverseInfer()
        ctx = make_ctx(raw_signals_payload=signals)
        result = step.execute(ctx)
        assert result.success is True

    def test_low_confidence_pause(self, make_ctx, mock_ai):
        mock_ai.set_response("reverse_infer", {
            "inferred_capabilities": [
                {
                    "name": "未知功能",
                    "key": "unknown",
                    "description": "无法确定的功能",
                    "confidence": 0.3,
                    "supporting_evidence": "模糊的UI元素",
                }
            ],
            "uncertain_questions": [
                {"question": "这是什么功能？", "context": "页面1", "suggested_answer": ""},
            ],
            "overall_confidence": 0.4,
            "analysis_summary": "无法确定业务能力",
        })
        step = ReverseInfer()
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(1))
        result = step.execute(ctx)

        assert result.success is True
        assert result.pause_for_confirmation is True
        assert result.confirmation_payload is not None
        assert len(result.confirmation_payload["questions"]) == 1

    def test_no_ui_info(self, make_ctx):
        signals = _make_raw_signals(1)
        signals["ui_descriptions"] = []
        signals["ui_specs"] = []
        signals["has_ui"] = False

        step = ReverseInfer()
        ctx = make_ctx(raw_signals_payload=signals)
        result = step.execute(ctx)
        assert result.success is False
        assert "无 UI 信息" in (result.error or "")

    def test_invalid_json_response(self, make_ctx, mock_ai):
        mock_ai.set_response("reverse_infer", "not valid json at all")
        step = ReverseInfer()
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(1))
        result = step.execute(ctx)
        assert result.success is False
        assert "非有效 JSON" in (result.error or "")

    def test_missing_signals(self, make_ctx):
        step = ReverseInfer()
        ctx = make_ctx()
        result = step.execute(ctx)
        assert result.success is False
        assert "缺少 raw_signals" in (result.error or "")

    def test_missing_project_id(self, make_ctx):
        signals = _make_raw_signals(1)
        del signals["project_id"]
        step = ReverseInfer()
        ctx = make_ctx(raw_signals_payload=signals)
        result = step.execute(ctx)
        assert result.success is False
        assert "缺少 project_id" in (result.error or "")


class TestExecuteOldProject:
    def test_success(self, make_ctx, mock_ai):
        mock_ai.set_response("reverse_infer", {
            "change_summary": {
                "new_capabilities": [
                    {
                        "name": "验证码校验",
                        "key": "captcha_verify",
                        "description": "登录时需输入图形验证码",
                        "confidence": 0.9,
                        "supporting_evidence": "登录页新增captcha输入框和验证码图片",
                    }
                ],
                "modified_capabilities": [
                    {
                        "old_key": "user_auth",
                        "old_name": "用户认证",
                        "new_name": "用户认证",
                        "change_description": "登录流程增加验证码校验步骤",
                        "change_type": "business_logic",
                        "confidence": 0.85,
                    }
                ],
                "removed_capabilities": [],
                "ui_only_changes": "登录按钮样式从蓝色变为绿色",
            },
            "uncertain_questions": [
                {
                    "question": "验证码是否有失效时间？",
                    "context": "登录页",
                    "suggested_answer": "通常60秒失效",
                }
            ],
            "overall_confidence": 0.85,
            "analysis_summary": "主要变更为登录增加验证码校验",
        })
        step = ReverseInfer()
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(1),
            fingerprints_payload=_make_fingerprints(1),
        )
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "inferred_business_summary"
        assert result.artifact_payload is not None
        assert result.artifact_payload["mode"] == "old_project"
        assert result.artifact_payload["is_old_project"] is True
        assert result.artifact_payload["confidence"] == 0.85
        assert result.pause_for_confirmation is False

    def test_low_confidence_pause(self, make_ctx, mock_ai):
        mock_ai.set_response("reverse_infer", {
            "change_summary": {
                "new_capabilities": [],
                "modified_capabilities": [],
                "removed_capabilities": [],
                "ui_only_changes": "",
            },
            "uncertain_questions": [
                {"question": "完全不确定变更内容", "context": "全部页面", "suggested_answer": ""},
            ],
            "overall_confidence": 0.3,
            "analysis_summary": "无法确定变更",
        })
        step = ReverseInfer()
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(1),
            fingerprints_payload=_make_fingerprints(1),
        )
        result = step.execute(ctx)

        assert result.success is True
        assert result.pause_for_confirmation is True
        assert result.confirmation_payload is not None

    def test_empty_fingerprints(self, make_ctx, mock_ai):
        """空指纹列表（total_count=0）视为新项目模式"""
        mock_ai.set_response("reverse_infer", {
            "inferred_capabilities": [
                {
                    "name": "用户认证",
                    "key": "user_auth",
                    "description": "用户登录",
                    "confidence": 0.9,
                    "supporting_evidence": "登录页控件",
                }
            ],
            "uncertain_questions": [],
            "overall_confidence": 0.9,
            "analysis_summary": "包含认证能力",
        })
        empty_fp = {
            "project_id": 1,
            "fingerprints": [],
            "total_count": 0,
            "stale_backfilled_count": 0,
        }
        step = ReverseInfer()
        ctx = make_ctx(
            raw_signals_payload=_make_raw_signals(1),
            fingerprints_payload=empty_fp,
        )
        result = step.execute(ctx)
        assert result.success is True
        assert result.artifact_payload["mode"] == "new_project"


# ==================== 纯函数测试 ====================

class TestHashDict:
    def test_dict(self):
        result = _hash_dict({"a": 1, "b": 2})
        assert isinstance(result, str)
        assert len(result) == 16

    def test_list(self):
        result = _hash_dict([1, 2, 3])
        assert isinstance(result, str)

    def test_arbitrary_object(self):
        result = _hash_dict(object())
        assert isinstance(result, str)
        assert len(result) == 16


class TestClampFloat:
    def test_normal(self):
        assert _clamp_float(0.5, 0.0, 1.0) == 0.5

    def test_below_range(self):
        assert _clamp_float(-1.0, 0.0, 1.0) == 0.0

    def test_above_range(self):
        assert _clamp_float(2.0, 0.0, 1.0) == 1.0

    def test_non_numeric(self):
        assert _clamp_float("abc", 0.0, 1.0) == 0.0

    def test_none(self):
        assert _clamp_float(None, 0.0, 1.0) == 0.0


class TestBuildUiText:
    def test_with_descriptions_and_specs(self):
        signals = _make_raw_signals(1)
        text = _build_ui_text(signals["ui_descriptions"], signals["ui_specs"])
        assert "登录页" in text
        assert "注册页" in text
        assert "username" in text

    def test_empty(self):
        text = _build_ui_text([], [])
        assert text == ""


class TestBuildFingerprintText:
    def test_with_data(self):
        fp = _make_fingerprints(1)
        text = _build_fingerprint_text(fp)
        assert "用户管理" in text
        assert "订单管理" in text
        assert "旧用例摘要" in text

    def test_none(self):
        assert _build_fingerprint_text(None) == "（无历史用例指纹）"

    def test_empty_list(self):
        fp = {"fingerprints": [], "total_count": 0}
        assert _build_fingerprint_text(fp) == "（无历史用例指纹）"


class TestParseInferResponse:
    def test_valid_dict(self):
        parsed = _parse_infer_response('{"overall_confidence": 0.8}')
        assert parsed == {"overall_confidence": 0.8}

    def test_valid_array(self):
        parsed = _parse_infer_response('[{"name": "test", "key": "t", "description": "d", "confidence": 0.9}]')
        assert parsed is not None
        assert "inferred_capabilities" in parsed
        assert parsed["overall_confidence"] == 0.5

    def test_invalid_json(self):
        assert _parse_infer_response("not json") is None

    def test_json_in_text(self):
        parsed = _parse_infer_response('一些文本 {"overall_confidence": 0.7} 更多文本')
        assert parsed is not None
        assert parsed["overall_confidence"] == 0.7


class TestValidateNewProjectOutput:
    def test_valid(self):
        ok, err = _validate_new_project_output({
            "inferred_capabilities": [
                {
                    "name": "test",
                    "key": "t",
                    "description": "desc",
                    "confidence": 0.9,
                }
            ],
            "uncertain_questions": [],
            "overall_confidence": 0.9,
        })
        assert ok is True
        assert err is None

    def test_missing_confidence(self):
        ok, err = _validate_new_project_output({
            "inferred_capabilities": [],
            "uncertain_questions": [],
        })
        assert ok is False
        assert "overall_confidence" in (err or "")

    def test_capabilities_not_list(self):
        ok, err = _validate_new_project_output({
            "inferred_capabilities": "not a list",
            "uncertain_questions": [],
            "overall_confidence": 0.9,
        })
        assert ok is False

    def test_capability_missing_field(self):
        ok, err = _validate_new_project_output({
            "inferred_capabilities": [{"name": "test"}],
            "uncertain_questions": [],
            "overall_confidence": 0.9,
        })
        assert ok is False
        assert "缺少" in (err or "")

    def test_questions_not_list(self):
        ok, err = _validate_new_project_output({
            "inferred_capabilities": [],
            "uncertain_questions": "not a list",
            "overall_confidence": 0.9,
        })
        assert ok is False


class TestValidateOldProjectOutput:
    def test_valid(self):
        ok, err = _validate_old_project_output({
            "change_summary": {
                "new_capabilities": [],
                "modified_capabilities": [],
                "removed_capabilities": [],
            },
            "uncertain_questions": [],
            "overall_confidence": 0.9,
        })
        assert ok is True
        assert err is None

    def test_missing_change_summary(self):
        ok, err = _validate_old_project_output({
            "uncertain_questions": [],
            "overall_confidence": 0.9,
        })
        assert ok is False

    def test_change_summary_not_dict(self):
        ok, err = _validate_old_project_output({
            "change_summary": "not a dict",
            "uncertain_questions": [],
            "overall_confidence": 0.9,
        })
        assert ok is False

    def test_sub_field_not_list(self):
        ok, err = _validate_old_project_output({
            "change_summary": {
                "new_capabilities": "not a list",
                "modified_capabilities": [],
                "removed_capabilities": [],
            },
            "uncertain_questions": [],
            "overall_confidence": 0.9,
        })
        assert ok is False

    def test_questions_not_list(self):
        ok, err = _validate_old_project_output({
            "change_summary": {
                "new_capabilities": [],
                "modified_capabilities": [],
                "removed_capabilities": [],
            },
            "uncertain_questions": "not a list",
            "overall_confidence": 0.9,
        })
        assert ok is False
