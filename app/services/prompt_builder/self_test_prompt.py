"""Self-test prompt helpers for AI test case generation."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

TESTID_MAP_PATH = Path("docs/testid-map.json")

SELF_TEST_LOCATOR_MAP_FALLBACK = """## 平台元素定位器映射
以下元素已配置 data-testid，生成自测用例时优先使用这些稳定定位器：
- 用户名输入框: [data-testid="login-username"]
- 密码输入框: [data-testid="login-password"]
- 登录按钮: [data-testid="login-submit"]
- 创建项目按钮: [data-testid="create-project"]
- 项目卡片: [data-testid="project-card"]
- 用例搜索框: [data-testid="case-search"]
- 创建用例按钮: [data-testid="create-case"]
- 执行按钮: [data-testid="execute-btn"]
- 停止按钮: [data-testid="stop-btn"]
- 项目导航: [data-testid="nav-/home/project"]"""

SELF_TEST_ASSERTION_SYNTAX = """## 结构化断言语法
自测用例的 expected_result 必须优先使用可执行断言表达：
- [text_contains] 页面包含指定文案
- [text_equals] 文案完全匹配
- [text_matches] 文案满足正则
- [visible] 元素可见
- [not_visible] 元素不可见
- [url_contains] URL 包含路径片段
- [url_equals] URL 完全匹配"""

SELF_TEST_NAVIGATION_GUIDE = """## 导航说明
平台前端使用 History 模式，导航路径不带 #/ 前缀。
- action_type 使用 navigate 表示页面跳转
- 导航到项目页时 target_element 使用 /home/project
- 导航到用例页时 target_element 使用 /home/case
- 不使用 #/home/project 这类 hash 路径"""

SELF_TEST_CORE_FLOWS = """## 必须覆盖的核心流程
- 登录流程
- 项目管理
- 测试点提取
- 用例生成
- 任务执行
- 报告查看"""


def _format_testid_entries(testids: List[Dict[str, Any]]) -> str:
    lines = [
        "## 平台元素定位器映射",
        "以下元素已配置 data-testid，生成自测用例时优先使用这些稳定定位器：",
    ]
    for item in testids:
        selector = item.get("selector") or (
            f'[data-testid="{item.get("id", "")}"]' if item.get("id") else ""
        )
        if not selector:
            continue
        context = (item.get("context") or "").strip()
        if context:
            lines.append(f"- {context}: {selector}")
        else:
            lines.append(f"- {selector}")
    return "\n".join(lines)


def load_testid_map() -> str:
    if not TESTID_MAP_PATH.exists():
        return SELF_TEST_LOCATOR_MAP_FALLBACK
    try:
        data = json.loads(TESTID_MAP_PATH.read_text(encoding="utf-8"))
    except Exception:
        return SELF_TEST_LOCATOR_MAP_FALLBACK

    testids = data.get("testids")
    if not isinstance(testids, list) or not testids:
        return "\n".join([
            "## 平台元素定位器映射",
            "以下元素已配置 data-testid，当前未发现动态映射条目。",
            SELF_TEST_LOCATOR_MAP_FALLBACK,
        ])
    return _format_testid_entries(testids)


def build_self_test_prompt(
    requirement_content: str,
    ui_description: str,
    module: str,
    function: str,
    point: str,
    priority: int,
    ui_specs: Optional[List[Dict[str, Any]]] = None,
    history_cases: Optional[List[Dict[str, Any]]] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> str:
    from app.services.prompt_builder.builder import PromptBuilder

    base_prompt = PromptBuilder.build_linear_prompt(
        requirement_content=requirement_content,
        ui_description=ui_description,
        module=module,
        function=function,
        point=point,
        priority=priority,
        ui_specs=ui_specs,
        extra_context=extra_context,
    )

    sections = [
        base_prompt,
        load_testid_map(),
        SELF_TEST_ASSERTION_SYNTAX,
        SELF_TEST_NAVIGATION_GUIDE,
        SELF_TEST_CORE_FLOWS,
        "## 自测项目约束\n- 优先生成 ui_automation 用例\n- 优先使用 data-testid 定位器\n- 每个步骤必须可自动执行和断言",
    ]

    if history_cases:
        sections.append("## 历史用例参考")
        for case in history_cases[:20]:
            title = case.get("title") or case.get("case_title") or ""
            module_name = case.get("module") or ""
            sections.append(f"- [{module_name}] {title}".strip())

    return "\n\n".join(sections)


__all__ = [
    "TESTID_MAP_PATH",
    "SELF_TEST_LOCATOR_MAP_FALLBACK",
    "SELF_TEST_ASSERTION_SYNTAX",
    "SELF_TEST_NAVIGATION_GUIDE",
    "SELF_TEST_CORE_FLOWS",
    "load_testid_map",
    "build_self_test_prompt",
]
