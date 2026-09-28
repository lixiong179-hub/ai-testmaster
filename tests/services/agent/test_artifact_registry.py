"""ArtifactRegistry 与 6 个内置 Artifact 单元测试。

覆盖 8 个用例：
    1. register → list_artifacts 含注册类型
    2. validate 合法数据 → 返回 Artifact 实例
    3. validate 非法数据 → 抛 ValidationError
    4. validate 未知类型 → 抛 KeyError
    5. build_artifacts_index_prompt 含所有类型与描述
    6. 每个 Artifact 子类 to_prompt_section 输出格式正确
    7. Artifact 子类 ClassVar 字段正确
    8. Pydantic extra="forbid" 拒绝未知字段

测试原则：纯内存操作，无需数据库。
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.agent.artifact_registry import ArtifactRegistry
from app.services.agent.artifacts import (
    ApplicationStateArtifact,
    Artifact,
    ExecutionStateArtifact,
    FailureHistoryArtifact,
    FailureRecord,
    ProjectContextArtifact,
    TestCaseArtifact,
    UserIntentArtifact,
)


# ── Fixtures ──


@pytest.fixture
def registry_with_all_artifacts() -> ArtifactRegistry:
    """注册全部 6 个内置 Artifact 的注册表。"""
    registry = ArtifactRegistry()
    registry.register(TestCaseArtifact)
    registry.register(UserIntentArtifact)
    registry.register(ProjectContextArtifact)
    registry.register(ExecutionStateArtifact)
    registry.register(FailureHistoryArtifact)
    registry.register(ApplicationStateArtifact)
    return registry


# ── 用例 1-5：ArtifactRegistry 行为 ──


def test_register_then_list_contains_type() -> None:
    """用例1: register(TestCaseArtifact) → list_artifacts() 含 "test_case"。"""
    registry = ArtifactRegistry()
    registry.register(TestCaseArtifact)
    assert "test_case" in registry.list_artifacts()


def test_validate_returns_artifact_instance(registry_with_all_artifacts: ArtifactRegistry) -> None:
    """用例2: validate 合法数据 → 返回 TestCaseArtifact 实例。"""
    artifact = registry_with_all_artifacts.validate("test_case", {
        "title": "登录测试",
        "steps": [{"action": "click", "target": "#login"}],
        "preconditions": ["用户已注册"],
    })
    assert isinstance(artifact, TestCaseArtifact)
    assert artifact.title == "登录测试"
    assert len(artifact.steps) == 1
    assert artifact.preconditions == ["用户已注册"]


def test_validate_invalid_data_raises_validation_error(registry_with_all_artifacts: ArtifactRegistry) -> None:
    """用例3: validate 缺少必填字段 → 抛 ValidationError。"""
    # TestCaseArtifact 必填 title 与 steps
    with pytest.raises(ValidationError):
        registry_with_all_artifacts.validate("test_case", {"steps": []})


def test_validate_unknown_type_raises_key_error(registry_with_all_artifacts: ArtifactRegistry) -> None:
    """用例4: validate 未知 artifact_type → 抛 KeyError。"""
    with pytest.raises(KeyError):
        registry_with_all_artifacts.validate("unknown_type", {})


def test_build_artifacts_index_prompt_contains_all(registry_with_all_artifacts: ArtifactRegistry) -> None:
    """用例5: build_artifacts_index_prompt 含所有 artifact_type 与 description。"""
    prompt = registry_with_all_artifacts.build_artifacts_index_prompt()
    assert "test_case" in prompt
    assert "user_intent" in prompt
    assert "project_context" in prompt
    assert "execution_state" in prompt
    assert "failure_history" in prompt
    assert "application_state" in prompt
    # description 也应被注入
    assert "测试用例上下文" in prompt
    assert "用户自然语言请求" in prompt
    # 头部标题与尾部说明
    assert "# Available Artifacts" in prompt


# ── 用例 6-7：Artifact 子类 to_prompt_section 与 ClassVar ──


_ARTIFACT_CASES = [
    (TestCaseArtifact, {"title": "登录测试", "steps": [{"action": "click"}]}),
    (UserIntentArtifact, {"natural_language_request": "生成登录用例"}),
    (ProjectContextArtifact, {"project_id": 1, "name": "demo"}),
    (ExecutionStateArtifact, {"current_step": "click #login"}),
    (FailureHistoryArtifact, {"recent_failures": [{"failure_type": "element_gone"}]}),
    (ApplicationStateArtifact, {"url": "http://example.com"}),
]


@pytest.mark.parametrize("artifact_class, valid_data", _ARTIFACT_CASES)
def test_to_prompt_section_format(artifact_class: type, valid_data: dict) -> None:
    """用例6: 每个 Artifact 子类 to_prompt_section 输出含类型标识、描述与 JSON 块。"""
    artifact = artifact_class.model_validate(valid_data)
    section = artifact.to_prompt_section()
    assert f"[Artifact: {artifact_class.artifact_type}]" in section
    assert artifact_class.description in section
    assert "```json" in section
    # JSON 块内含字段数据（至少出现 artifact_type 对应的字段名）
    assert isinstance(section, str) and len(section) > 0


@pytest.mark.parametrize(
    "artifact_class, expected_type, expected_desc_substring",
    [
        (TestCaseArtifact, "test_case", "测试用例"),
        (UserIntentArtifact, "user_intent", "用户"),
        (ProjectContextArtifact, "project_context", "项目"),
        (ExecutionStateArtifact, "execution_state", "执行"),
        (FailureHistoryArtifact, "failure_history", "失败"),
        (ApplicationStateArtifact, "application_state", "应用"),
    ],
)
def test_artifact_class_var_fields(artifact_class: type, expected_type: str, expected_desc_substring: str) -> None:
    """用例7: Artifact 子类 ClassVar 字段（artifact_type / description）正确。"""
    assert artifact_class.artifact_type == expected_type
    assert expected_desc_substring in artifact_class.description


# ── 用例 8：extra="forbid" 行为 ──


def test_artifact_extra_forbid_rejects_unknown_field(registry_with_all_artifacts: ArtifactRegistry) -> None:
    """用例8: Pydantic extra='forbid' 传入未定义字段抛 ValidationError。"""
    with pytest.raises(ValidationError):
        registry_with_all_artifacts.validate("test_case", {
            "title": "t",
            "steps": [],
            "unknown_field": "should_be_rejected",
        })


# ── 附加边界用例：空注册表 build_artifacts_index_prompt 返回空串 ──


def test_build_artifacts_index_prompt_empty_when_no_registry() -> None:
    """边界用例: 未注册任何 Artifact 时 build_artifacts_index_prompt 返回空串。"""
    registry = ArtifactRegistry()
    assert registry.build_artifacts_index_prompt() == ""
    assert registry.list_artifacts() == []


# ── 附加边界用例：重复注册抛 ValueError ──


def test_register_duplicate_raises_value_error() -> None:
    """边界用例: 重复注册同一 artifact_type 抛 ValueError。"""
    registry = ArtifactRegistry()
    registry.register(TestCaseArtifact)
    with pytest.raises(ValueError):
        registry.register(TestCaseArtifact)


# ── 附加边界用例：FailureRecord 嵌套模型 ──


def test_failure_history_with_nested_records(registry_with_all_artifacts: ArtifactRegistry) -> None:
    """边界用例: FailureHistoryArtifact 含嵌套 FailureRecord 列表。"""
    artifact = registry_with_all_artifacts.validate("failure_history", {
        "recent_failures": [
            {
                "failure_type": "element_gone",
                "selector": "#btn",
                "healed_selector": "#btn-new",
                "confidence": 0.92,
                "strategy": "mcp",
            },
        ],
    })
    assert isinstance(artifact, FailureHistoryArtifact)
    assert len(artifact.recent_failures) == 1
    record = artifact.recent_failures[0]
    assert isinstance(record, FailureRecord)
    assert record.failure_type == "element_gone"
    assert record.confidence == 0.92
    assert record.strategy == "mcp"
