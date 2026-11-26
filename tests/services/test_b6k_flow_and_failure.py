"""B6k 护栏：UI 原型流程 Prompt 拼装与失败原因分类。"""

from types import SimpleNamespace

import pytest

from app.models.enums import LocatorStatus
from app.services.execution_core.failure_analysis import _perform_failure_analysis_with_steps
from app.services.prompt_builder.case_prompt._flow_builder import _append_nested_flow


def node(screen_id, name, elements=None, summary="", image_url=None, flow_meta=None):
    data = {"screen_id": screen_id, "screen_name": name, "ui_spec_elements": elements or []}
    if summary:
        data["summary"] = summary
    if image_url:
        data["image_url"] = image_url
    if flow_meta:
        data["flow_meta"] = flow_meta
    return data


LOGIN_ELEMENTS = [
    {"type": "input", "label": "账号", "interactive": True},
    {"type": "input", "label": "密码", "interactive": True},
    {"type": "button", "label": "登录", "interactive": True},
    {"type": "button", "label": "忘记密码", "interactive": True},
]


def build_parts(
    main_nodes,
    node_map=None,
    branch=None,
    exception=None,
    bypass=None,
    include_images=False,
) -> str:
    parts: list[str] = []
    _append_nested_flow(
        parts,
        main_nodes,
        node_map or {n["screen_id"]: n for n in main_nodes},
        branch or {},
        exception or {},
        bypass or {},
        include_images,
    )
    return "\n".join(parts)


class TestAppendNestedFlowMain:
    def test_header_and_main_step(self):
        text = build_parts([node(1, "登录", LOGIN_ELEMENTS, summary=" 用户登录 ")])

        assert "## UI原型图流程结构" in text
        assert "### 场景1: 主干正向流程" in text
        assert "步骤 1: [截图1 - 登录]" in text
        assert "input:账号" in text
        assert "摘要:用户登录" in text
        assert "场景2" not in text

    def test_image_ref_requires_flag_and_url(self):
        without_flag = build_parts([node(1, "登录", image_url="http://img/1.png")])
        with_flag = build_parts([node(1, "登录", image_url="http://img/1.png")], include_images=True)

        assert "图片URL" not in without_flag
        assert "图片URL: http://img/1.png" in with_flag

    def test_empty_elements_and_summary(self):
        text = build_parts([node(1, "空白页")])

        assert "步骤 1: [截图1 - 空白页] 元素: " in text
        assert "摘要:" not in text

    def test_single_bypass_hint(self):
        nodes = [node(1, "登录"), node(9, "广告弹窗")]
        text = build_parts(nodes, bypass={1: [{"target": 9}]})

        assert "此步骤可能出现广告弹窗，需关闭弹窗后验证主流程页面元素仍可正常交互" in text

    def test_multiple_bypass_hint_is_numbered(self):
        nodes = [node(1, "登录"), node(9, "活动弹窗"), node(10, "更新提示")]
        text = build_parts(nodes, bypass={1: [{"target": 9}, {"target": 10}]})

        assert "1. 活动弹窗; 2. 更新提示" in text

    def test_bypass_target_missing_falls_back_to_popup(self):
        text = build_parts([node(1, "登录")], bypass={1: [{"target": 404}]})

        assert "此步骤可能出现弹窗" in text


class TestAppendNestedFlowChildren:
    def test_branch_scene(self):
        nodes = [node(1, "登录", LOGIN_ELEMENTS), node(2, "注册")]
        text = build_parts(nodes, branch={1: [{"target": 2, "condition": "点击注册"}]})

        assert "### 场景2: 分支流程（源于步骤1[登录]，case_category=boundary）" in text
        assert "触发条件: 点击注册（用户填写）" in text
        assert "起始点: 从步骤1[登录]触发分支，进入 [注册]" in text
        assert "depends_on 必须填写场景1的用例标题" in text
        assert "anchor_step 必须填写1" in text
        assert "可见账号|状态、密码|状态、登录|状态等元素" in text

    def test_exception_scene(self):
        nodes = [node(1, "登录"), node(3, "错误提示")]
        text = build_parts(nodes, exception={1: [{"target": 3}]})

        assert "### 场景2: 异常流程（源于步骤1[登录]，case_category=exception）" in text
        assert "错误提示操作失败或系统异常（系统推断）" in text

    def test_invalid_target_is_skipped(self):
        nodes = [node(1, "登录"), node(2, "注册")]
        text = build_parts(nodes, branch={1: [{"target": None}, {"target": "abc"}]})

        assert "### 场景2" not in text

    def test_scene_index_increments_across_edges(self):
        nodes = [node(1, "登录"), node(2, "注册"), node(3, "找回密码")]
        text = build_parts(nodes, branch={1: [{"target": 2}, {"target": 3}]})

        assert "### 场景2: 分支流程" in text
        assert "### 场景3: 分支流程" in text

    def test_empty_source_elements_hint(self):
        nodes = [node(1, "登录"), node(2, "注册")]
        text = build_parts(nodes, branch={1: [{"target": 2}]})

        assert "可见页面已加载完成等元素" in text

    def test_flow_meta_and_edge_hints(self):
        nodes = [
            node(1, "登录"),
            node(2, "弹窗", flow_meta={"pre_action": "等待加载", "expected_result": "出现弹窗"}),
        ]
        edge = {"target": 2, "trigger_action": "点击广告", "note": "仅首次"}
        text = build_parts(nodes, branch={1: [edge]})

        assert "前置操作: 等待加载" in text
        assert "预期结果: 出现弹窗" in text
        assert "连线触发动作: 点击广告" in text
        assert "连线备注: 仅首次" in text


class TestAppendNestedFlowBypassSection:
    def test_bypass_section_rendered(self):
        nodes = [node(1, "登录"), node(9, "广告弹窗")]
        text = build_parts(nodes, bypass={1: [{"target": 9}]})

        assert "### 场景2: 旁路流程（弹窗/浮层拦截，case_category=boundary）" in text
        assert "旁路说明: 旁路是主流程执行中自动弹出的干扰性弹窗或浮层" in text
        assert "- 步骤1[登录]:" in text
        assert "关闭[广告弹窗]后继续主流程" in text

    def test_bypass_section_uses_scene_index_after_children(self):
        nodes = [node(1, "登录"), node(2, "注册"), node(9, "广告弹窗")]
        text = build_parts(nodes, branch={1: [{"target": 2}]}, bypass={1: [{"target": 9}]})

        assert "### 场景2: 分支流程" in text
        assert "### 场景3: 旁路流程" in text

    def test_no_bypass_section_without_edges(self):
        text = build_parts([node(1, "登录")])

        assert "旁路流程" not in text


def make_result(error_msg="", exec_log="", ai_analysis="", screenshot_url=None):
    return SimpleNamespace(
        id=11,
        error_msg=error_msg,
        exec_log=exec_log,
        ai_analysis=ai_analysis,
        screenshot_url=screenshot_url,
    )


TEST_CASE = SimpleNamespace(id=22, title="登录用例")


def make_step(step_number=1, locator_status="", has_locator=1, action_type="verify"):
    return SimpleNamespace(
        step_number=step_number,
        locator_status=locator_status,
        has_locator=has_locator,
        action_type=action_type,
    )


class TestFailureAnalysisClassification:
    def test_locator_keyword_marks_case_issue(self):
        analysis = _perform_failure_analysis_with_steps(make_result(error_msg="元素未找到: #submit"), TEST_CASE, [])

        assert analysis["suggested_type"] == "case_issue"
        assert "元素未找到" in analysis["case_issue_indicators"][0]
        assert analysis["confidence"] == 0.65

    def test_case_keyword_in_ai_analysis(self):
        analysis = _perform_failure_analysis_with_steps(make_result(ai_analysis="需要修改用例"), TEST_CASE, [])

        assert any("用例问题关键词" in item for item in analysis["case_issue_indicators"])
        assert analysis["suggested_type"] == "case_issue"

    def test_bug_keyword_marks_product_bug(self):
        analysis = _perform_failure_analysis_with_steps(make_result(error_msg="页面显示异常"), TEST_CASE, [])

        assert analysis["suggested_type"] == "product_bug"
        assert "Bug问题关键词" in analysis["bug_issue_indicators"][0]

    def test_failed_locator_step(self):
        step = make_step(locator_status=LocatorStatus.FAILED.value)

        analysis = _perform_failure_analysis_with_steps(make_result(), TEST_CASE, [step])

        assert "步骤1定位状态为失败" in analysis["case_issue_indicators"]

    def test_missing_locator_for_interactive_step(self):
        analysis = _perform_failure_analysis_with_steps(
            make_result(), TEST_CASE, [make_step(action_type="click", has_locator=0)]
        )

        assert "步骤1需要元素定位但缺少定位信息" in analysis["case_issue_indicators"]

    def test_missing_locator_for_non_interactive_step_ignored(self):
        analysis = _perform_failure_analysis_with_steps(
            make_result(), TEST_CASE, [make_step(action_type="verify", has_locator=0)]
        )

        assert analysis["case_issue_indicators"] == []

    def test_ai_analysis_suggestions(self):
        analysis = _perform_failure_analysis_with_steps(make_result(ai_analysis="请调整步骤并更新定位"), TEST_CASE, [])

        assert "AI分析建议修改用例内容" in analysis["case_issue_indicators"]

    def test_ai_analysis_bug_hint(self):
        analysis = _perform_failure_analysis_with_steps(make_result(ai_analysis="可能是缺陷"), TEST_CASE, [])

        assert "AI分析提示可能是产品Bug" in analysis["bug_issue_indicators"]

    def test_tie_requires_review(self):
        analysis = _perform_failure_analysis_with_steps(
            make_result(ai_analysis="建议修改用例，但可能是bug"), TEST_CASE, []
        )

        assert analysis["suggested_type"] == "needs_review"
        assert analysis["confidence"] == 0.4
        assert "人工进一步判断" in analysis["reason"]

    def test_nothing_matched_requires_review(self):
        analysis = _perform_failure_analysis_with_steps(make_result(), TEST_CASE, [])

        assert analysis["suggested_type"] == "needs_review"
        assert analysis["confidence"] == 0.3

    def test_confidence_is_capped(self):
        analysis = _perform_failure_analysis_with_steps(
            make_result(ai_analysis="建议修改用例，请调整步骤，更新定位，修改预期"), TEST_CASE, []
        )

        assert analysis["confidence"] <= 0.95

    def test_result_fields_passthrough(self):
        analysis = _perform_failure_analysis_with_steps(
            make_result(error_msg="err", exec_log="log", ai_analysis="ai", screenshot_url="http://shot"),
            TEST_CASE,
            [],
        )

        assert analysis["result_id"] == 11
        assert analysis["case_id"] == 22
        assert analysis["case_title"] == "登录用例"
        assert analysis["error_msg"] == "err"
        assert analysis["ai_analysis"] == "ai"
        assert analysis["screenshot_url"] == "http://shot"
        assert "T" in analysis["analysis_time"]

    def test_multiple_failed_steps_accumulate(self):
        steps = [make_step(1, LocatorStatus.FAILED.value), make_step(2, LocatorStatus.FAILED.value)]

        analysis = _perform_failure_analysis_with_steps(make_result(), TEST_CASE, steps)

        assert len(analysis["case_issue_indicators"]) == 2
        assert analysis["confidence"] == pytest.approx(0.8)
