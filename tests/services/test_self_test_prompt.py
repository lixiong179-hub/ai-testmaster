"""自测用例 Prompt 构建单元测试
覆盖:
    - 自测 Prompt 包含 data-testid 映射表
    - 自测 Prompt 包含结构化断言语法说明
    - 自测 Prompt 包含 SPA 导航说明（History 模式，无 #/ 前缀）
    - 自测 Prompt 包含核心流程覆盖要求
    - 自测项目使用自测 Prompt，非自测项目使用普通 Prompt
    - PromptBuilder.for_self_test_case 返回正确结构
    - build_self_test_prompt 包含基础线性 Prompt 内容
    - _build_full_prompt 在 is_self_test=True 时使用自测 Prompt
    - _build_full_prompt 在 is_self_test=False 时使用普通 Prompt
    - load_testid_map 从 JSON 文件读取映射
    - load_testid_map 在 JSON 不存在时回退到默认映射
    - load_testid_map 在 JSON 格式错误时回退到默认映射
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.services.prompt_builder.self_test_prompt import (
    build_self_test_prompt,
    load_testid_map,
    SELF_TEST_LOCATOR_MAP_FALLBACK,
    SELF_TEST_ASSERTION_SYNTAX,
    SELF_TEST_NAVIGATION_GUIDE,
    SELF_TEST_CORE_FLOWS,
    TESTID_MAP_PATH,
)
from app.services.prompt_builder import PromptBuilder
from app.pipelines.steps.case_generation import _build_full_prompt


def _make_tp(
    module: str = "登录模块",
    function: str = "登录功能",
    point: str = "验证正常登录流程",
    priority: int = 1,
) -> dict:
    return {
        "id": 1,
        "module": module,
        "function": function,
        "point": point,
        "priority": priority,
    }


# ── SELF_TEST_LOCATOR_MAP_FALLBACK 常量测试 ──────────────────


def test_locator_map_contains_login_username():
    assert '[data-testid="login-username"]' in SELF_TEST_LOCATOR_MAP_FALLBACK


def test_locator_map_contains_login_password():
    assert '[data-testid="login-password"]' in SELF_TEST_LOCATOR_MAP_FALLBACK


def test_locator_map_contains_login_submit():
    assert '[data-testid="login-submit"]' in SELF_TEST_LOCATOR_MAP_FALLBACK


def test_locator_map_contains_create_project():
    assert '[data-testid="create-project"]' in SELF_TEST_LOCATOR_MAP_FALLBACK


def test_locator_map_contains_project_card():
    assert '[data-testid="project-card"]' in SELF_TEST_LOCATOR_MAP_FALLBACK


def test_locator_map_contains_case_search():
    assert '[data-testid="case-search"]' in SELF_TEST_LOCATOR_MAP_FALLBACK


def test_locator_map_contains_create_case():
    assert '[data-testid="create-case"]' in SELF_TEST_LOCATOR_MAP_FALLBACK


def test_locator_map_contains_execute_btn():
    assert '[data-testid="execute-btn"]' in SELF_TEST_LOCATOR_MAP_FALLBACK


def test_locator_map_contains_stop_btn():
    assert '[data-testid="stop-btn"]' in SELF_TEST_LOCATOR_MAP_FALLBACK


def test_locator_map_contains_nav_item():
    assert '[data-testid="nav-/home/project"]' in SELF_TEST_LOCATOR_MAP_FALLBACK


# ── SELF_TEST_ASSERTION_SYNTAX 常量测试 ─────────────────────


def test_assertion_syntax_contains_text_contains():
    assert "[text_contains]" in SELF_TEST_ASSERTION_SYNTAX


def test_assertion_syntax_contains_text_equals():
    assert "[text_equals]" in SELF_TEST_ASSERTION_SYNTAX


def test_assertion_syntax_contains_text_matches():
    assert "[text_matches]" in SELF_TEST_ASSERTION_SYNTAX


def test_assertion_syntax_contains_visible():
    assert "[visible]" in SELF_TEST_ASSERTION_SYNTAX


def test_assertion_syntax_contains_not_visible():
    assert "[not_visible]" in SELF_TEST_ASSERTION_SYNTAX


def test_assertion_syntax_contains_url_contains():
    assert "[url_contains]" in SELF_TEST_ASSERTION_SYNTAX


def test_assertion_syntax_contains_url_equals():
    assert "[url_equals]" in SELF_TEST_ASSERTION_SYNTAX


# ── SELF_TEST_NAVIGATION_GUIDE 常量测试 ─────────────────────


def test_navigation_guide_mentions_history_mode():
    assert "History" in SELF_TEST_NAVIGATION_GUIDE


def test_navigation_guide_no_hash_prefix():
    nav_lines = SELF_TEST_NAVIGATION_GUIDE.split("\n")
    for line in nav_lines:
        if "导航到" in line or "target_element" in line:
            assert "#/" not in line


def test_navigation_guide_contains_relative_path():
    assert "/home/project" in SELF_TEST_NAVIGATION_GUIDE


def test_navigation_guide_contains_navigate_action_type():
    assert "navigate" in SELF_TEST_NAVIGATION_GUIDE


# ── SELF_TEST_CORE_FLOWS 常量测试 ───────────────────────────


def test_core_flows_contains_login():
    assert "登录流程" in SELF_TEST_CORE_FLOWS


def test_core_flows_contains_project_management():
    assert "项目管理" in SELF_TEST_CORE_FLOWS


def test_core_flows_contains_testpoint_extraction():
    assert "测试点提取" in SELF_TEST_CORE_FLOWS


def test_core_flows_contains_case_generation():
    assert "用例生成" in SELF_TEST_CORE_FLOWS


def test_core_flows_contains_task_execution():
    assert "任务执行" in SELF_TEST_CORE_FLOWS


def test_core_flows_contains_report():
    assert "报告查看" in SELF_TEST_CORE_FLOWS


# ── build_self_test_prompt 集成测试 ──────────────────────────


def test_self_test_prompt_contains_locator_map():
    prompt = build_self_test_prompt(
        requirement_content="需求内容",
        ui_description="UI描述",
        module="登录模块",
        function="登录功能",
        point="验证正常登录",
        priority=1,
    )
    assert '[data-testid="login-username"]' in prompt
    assert '[data-testid="login-submit"]' in prompt


def test_self_test_prompt_contains_assertion_syntax():
    prompt = build_self_test_prompt(
        requirement_content="需求内容",
        ui_description="UI描述",
        module="登录模块",
        function="登录功能",
        point="验证正常登录",
        priority=1,
    )
    assert "[text_contains]" in prompt
    assert "[visible]" in prompt
    assert "[url_contains]" in prompt


def test_self_test_prompt_contains_navigation_guide():
    prompt = build_self_test_prompt(
        requirement_content="需求内容",
        ui_description="UI描述",
        module="登录模块",
        function="登录功能",
        point="验证正常登录",
        priority=1,
    )
    assert "History" in prompt
    assert "/home/project" in prompt
    nav_section_start = prompt.find("## 导航说明")
    nav_section_end = prompt.find("## 必须覆盖的核心流程")
    if nav_section_start > 0 and nav_section_end > nav_section_start:
        nav_section = prompt[nav_section_start:nav_section_end]
        assert "navigate" in nav_section


def test_self_test_prompt_contains_core_flows():
    prompt = build_self_test_prompt(
        requirement_content="需求内容",
        ui_description="UI描述",
        module="登录模块",
        function="登录功能",
        point="验证正常登录",
        priority=1,
    )
    assert "登录流程" in prompt
    assert "项目管理" in prompt
    assert "用例生成" in prompt


def test_self_test_prompt_contains_base_linear_content():
    prompt = build_self_test_prompt(
        requirement_content="平台需求文档",
        ui_description="登录页UI描述",
        module="登录模块",
        function="登录功能",
        point="验证正常登录",
        priority=1,
    )
    assert "资深测试工程师" in prompt
    assert "平台需求文档" in prompt


def test_self_test_prompt_contains_self_test_constraints():
    prompt = build_self_test_prompt(
        requirement_content="需求",
        ui_description="UI",
        module="模块",
        function="功能",
        point="测试点",
        priority=2,
    )
    assert "data-testid" in prompt
    assert "ui_automation" in prompt
    assert "结构化断言语法" in prompt


# ── PromptBuilder.for_self_test_case 测试 ────────────────────


def test_for_self_test_case_returns_dict_with_prompt():
    builder = PromptBuilder()
    result = builder.for_self_test_case(
        requirement_content="需求",
        ui_description="UI",
        module="模块",
        function="功能",
        point="测试点",
        priority=2,
    )
    assert isinstance(result, dict)
    assert "prompt" in result
    assert "weight_hint" in result
    assert result["weight_hint"] == "self_test"


def test_for_self_test_case_prompt_contains_self_test_sections():
    builder = PromptBuilder()
    result = builder.for_self_test_case(
        requirement_content="需求",
        ui_description="UI",
        module="模块",
        function="功能",
        point="测试点",
        priority=2,
    )
    prompt = result["prompt"]
    assert '[data-testid="login-username"]' in prompt
    assert "[text_contains]" in prompt
    assert "History" in prompt
    assert "登录流程" in prompt


# ── _build_full_prompt 自测 vs 非自测区分测试 ────────────────


def test_build_full_prompt_self_test_uses_self_test_prompt():
    tp = _make_tp()
    prompt_self = _build_full_prompt(
        tp=tp,
        prd_content="需求",
        ui_description="UI",
        ui_specs=[],
        is_self_test=True,
    )
    assert '[data-testid="login-username"]' in prompt_self
    assert "[text_contains]" in prompt_self
    assert "History" in prompt_self


def test_build_full_prompt_normal_does_not_contain_self_test_sections():
    tp = _make_tp()
    prompt_normal = _build_full_prompt(
        tp=tp,
        prd_content="需求",
        ui_description="UI",
        ui_specs=[],
        is_self_test=False,
    )
    assert '[data-testid="login-username"]' not in prompt_normal
    assert "[text_contains]" not in prompt_normal


def test_build_full_prompt_self_test_with_extra_context():
    tp = _make_tp()
    prompt = _build_full_prompt(
        tp=tp,
        prd_content="需求",
        ui_description="UI",
        ui_specs=[],
        is_self_test=True,
        task_type="modify",
        task_context={
            "original_case": {
                "title": "原有用例标题",
                "precondition": "前置条件",
                "steps_json": [],
                "expected_result": "预期结果",
            },
            "modification_hint": "修改原因说明",
        },
    )
    assert '[data-testid="login-username"]' in prompt
    assert "原有用例" in prompt
    assert "修改原因说明" in prompt


def test_build_full_prompt_self_test_create_with_history():
    tp = _make_tp()
    prompt = _build_full_prompt(
        tp=tp,
        prd_content="需求",
        ui_description="UI",
        ui_specs=[],
        is_self_test=True,
        task_type="create",
        history_cases=[
            {"title": "已有用例1", "module": "登录", "summary": "登录测试"},
        ],
    )
    assert '[data-testid="login-username"]' in prompt
    assert "已有用例" in prompt


# ── 边界场景测试 ─────────────────────────────────────────────


def test_self_test_prompt_with_empty_inputs():
    prompt = build_self_test_prompt(
        requirement_content="",
        ui_description="",
        module="",
        function="",
        point="",
        priority=3,
    )
    assert '[data-testid="login-username"]' in prompt
    assert len(prompt) > 500


def test_self_test_prompt_with_ui_specs():
    ui_specs = [
        {
            "screen_id": 1,
            "screen_name": "登录页",
            "ui_spec": {
                "purpose": "用户登录",
                "regions": {"form": {"elements": [{"type": "input", "label": "用户名"}]}},
            },
        }
    ]
    prompt = build_self_test_prompt(
        requirement_content="需求",
        ui_description="UI",
        module="登录",
        function="登录",
        point="登录验证",
        priority=1,
        ui_specs=ui_specs,
    )
    assert '[data-testid="login-username"]' in prompt
    assert "登录页" in prompt


def test_self_test_prompt_with_history_cases():
    history = [
        {"title": "正向-登录成功", "module": "登录", "status": "active"},
    ]
    prompt = build_self_test_prompt(
        requirement_content="需求",
        ui_description="UI",
        module="登录",
        function="登录",
        point="登录验证",
        priority=1,
        history_cases=history,
    )
    assert '[data-testid="login-username"]' in prompt
    assert "正向-登录成功" in prompt


def test_navigation_guide_uses_history_mode_not_hash():
    assert "History 模式" in SELF_TEST_NAVIGATION_GUIDE
    assert "/home/project" in SELF_TEST_NAVIGATION_GUIDE
    nav_lines = SELF_TEST_NAVIGATION_GUIDE.split("\n")
    example_lines = [l for l in nav_lines if "导航到" in l or "target_element" in l]
    for line in example_lines:
        assert "#/" not in line or "不使用" in line


# ── load_testid_map 动态加载测试 ────────────────────────────


def test_load_testid_map_fallback_when_file_not_exists():
    with patch.object(Path, "exists", return_value=False):
        result = load_testid_map()
    assert result == SELF_TEST_LOCATOR_MAP_FALLBACK
    assert '[data-testid="login-username"]' in result


def test_load_testid_map_reads_from_json():
    fake_data = {
        "generated_at": "2026-05-19T12:00:00",
        "testids": [
            {
                "id": "login-username",
                "selector": '[data-testid="login-username"]',
                "file": "src/views/login/index.vue",
                "context": "用户名输入框",
            },
            {
                "id": "login-password",
                "selector": '[data-testid="login-password"]',
                "file": "src/views/login/index.vue",
                "context": "密码输入框",
            },
        ],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(fake_data, tmp, ensure_ascii=False)
        tmp_path = tmp.name
    try:
        with patch.object(Path, "exists", return_value=True), \
             patch("app.services.prompt_builder.self_test_prompt.TESTID_MAP_PATH", Path(tmp_path)):
            result = load_testid_map()
        assert '[data-testid="login-username"]' in result
        assert '[data-testid="login-password"]' in result
        assert "用户名输入框" in result
        assert "密码输入框" in result
        assert "## 平台元素定位器映射" in result
    finally:
        os.unlink(tmp_path)


def test_load_testid_map_fallback_on_invalid_json():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write("{invalid json content")
        tmp_path = tmp.name
    try:
        with patch.object(Path, "exists", return_value=True), \
             patch("app.services.prompt_builder.self_test_prompt.TESTID_MAP_PATH", Path(tmp_path)):
            result = load_testid_map()
        assert result == SELF_TEST_LOCATOR_MAP_FALLBACK
    finally:
        os.unlink(tmp_path)


def test_load_testid_map_fallback_on_empty_testids():
    fake_data = {"generated_at": "2026-05-19T12:00:00", "testids": []}
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(fake_data, tmp, ensure_ascii=False)
        tmp_path = tmp.name
    try:
        with patch.object(Path, "exists", return_value=True), \
             patch("app.services.prompt_builder.self_test_prompt.TESTID_MAP_PATH", Path(tmp_path)):
            result = load_testid_map()
        assert "## 平台元素定位器映射" in result
        assert "以下元素已配置 data-testid" in result
    finally:
        os.unlink(tmp_path)


def test_load_testid_map_entry_without_context():
    fake_data = {
        "generated_at": "2026-05-19T12:00:00",
        "testids": [
            {
                "id": "some-btn",
                "selector": '[data-testid="some-btn"]',
                "file": "src/views/test/index.vue",
                "context": "",
            },
        ],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(fake_data, tmp, ensure_ascii=False)
        tmp_path = tmp.name
    try:
        with patch.object(Path, "exists", return_value=True), \
             patch("app.services.prompt_builder.self_test_prompt.TESTID_MAP_PATH", Path(tmp_path)):
            result = load_testid_map()
        assert '- [data-testid="some-btn"]' in result
    finally:
        os.unlink(tmp_path)


def test_load_testid_map_entry_with_context():
    fake_data = {
        "generated_at": "2026-05-19T12:00:00",
        "testids": [
            {
                "id": "login-submit",
                "selector": '[data-testid="login-submit"]',
                "file": "src/views/login/index.vue",
                "context": "登录按钮",
            },
        ],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(fake_data, tmp, ensure_ascii=False)
        tmp_path = tmp.name
    try:
        with patch.object(Path, "exists", return_value=True), \
             patch("app.services.prompt_builder.self_test_prompt.TESTID_MAP_PATH", Path(tmp_path)):
            result = load_testid_map()
        assert "- 登录按钮: [data-testid=\"login-submit\"]" in result
    finally:
        os.unlink(tmp_path)
