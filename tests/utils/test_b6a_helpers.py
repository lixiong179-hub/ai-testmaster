"""B6a 前置护栏：`ai_client_parser` 分类/候选提取与增强 Prompt 组装的既有行为。

拆分前先锁定行为，避免「判定重排」带来的静默漂移（策略页 §5「先补测试再拆」）。
"""

from app.utils.ai_client_enhanced._enhanced_prompt import _build_generation_prompt
from app.utils.ai_client_parser._category_infer import infer_action_type, infer_test_category
from app.utils.ai_client_parser._json_fixer import _extract_json_candidates

UI_ACTION_TYPES = ("click", "input")


class TestInferActionTypePriority:
    def test_input_wins_over_click(self):
        assert infer_action_type("输入账号后点击登录") == "input"

    def test_click_wins_over_navigate_when_earlier(self):
        # 关键词优先级：input > click > navigate > verify > wait > scroll > hover > select > refresh > keypress > captcha
        assert infer_action_type("点击打开页面") == "click"

    def test_navigate(self):
        assert infer_action_type("打开订单页") == "navigate"

    def test_verify(self):
        assert infer_action_type("验证金额正确") == "verify"

    def test_wait_scroll_hover_select(self):
        assert infer_action_type("等待3秒") == "wait"
        assert infer_action_type("滚动到底部") == "scroll"
        assert infer_action_type("悬停在菜单") == "hover"
        assert infer_action_type("选择下拉项") == "select"

    def test_refresh_keypress_captcha(self):
        assert infer_action_type("刷新页面") == "refresh"
        assert infer_action_type("按键回车") == "keypress"
        # 注意「验证」属更高优先级的 verify，此处用不含该词的表述锁定 captcha 分支
        assert infer_action_type("拖动滑块") == "captcha"

    def test_default_is_click(self):
        assert infer_action_type("做点什么") == "click"
        assert infer_action_type("") == "click"


class TestInferTestCategoryPriority:
    def test_security_beats_all(self):
        assert infer_test_category([{"action": "点击登录", "expected_result": "存在SQL注入风险"}]) == (
            "security",
            "security",
        )

    def test_performance_beats_api(self):
        assert infer_test_category([{"action": "调用接口", "expected_result": "响应时间小于2秒"}]) == (
            "performance",
            "performance",
        )

    def test_api(self):
        assert infer_test_category([{"action": "发送GET请求", "expected_result": "返回200"}]) == (
            "api_automation",
            "api_automation",
        )

    def test_manual_when_check_without_ui(self):
        # 只有「检查」类动词、无 UI 动作 → 手工用例
        assert infer_test_category([{"action": "检查数据库记录", "expected_result": "记录存在"}]) == (
            "manual",
            "manual",
        )

    def test_manual_keyword(self):
        assert infer_test_category([{"action": "人工核对账单", "expected_result": "一致"}]) == ("manual", "manual")

    def test_ui_by_action_type(self):
        assert infer_test_category([{"action": "提交表单", "action_type": "click", "expected_result": "提交成功"}]) == (
            "ui_automation",
            "ui_automation",
        )

    def test_ui_default_when_check_has_ui(self):
        assert infer_test_category([{"action": "检查页面", "action_type": "input"}]) == (
            "ui_automation",
            "ui_automation",
        )

    def test_empty_steps_defaults_to_ui(self):
        assert infer_test_category([]) == ("ui_automation", "ui_automation")


class TestExtractJsonCandidates:
    def test_fenced_block_first_then_raw(self):
        raw = '前言\n```json\n{"a": 1}\n```\n尾巴'
        candidates = list(_extract_json_candidates(raw))
        assert candidates[0] == '{"a": 1}'
        assert candidates[1] == raw.strip()

    def test_span_order_largest_first(self):
        candidates = list(_extract_json_candidates('补充 {"a": {"b": 1}} 结束'))
        spans = [c for c in candidates if c.startswith("{") and c != '补充 {"a": {"b": 1}} 结束']
        assert spans[0] == '{"a": {"b": 1}}'

    def test_braces_inside_string_ignored(self):
        candidates = list(_extract_json_candidates('{"a": "}{"}'))
        assert '{"a": "}{"}' in candidates

    def test_escaped_quote_handling(self):
        candidates = list(_extract_json_candidates('{"a": "he said \\"hi\\""}'))
        assert '{"a": "he said \\"hi\\""}' in candidates

    def test_array_spans_extracted(self):
        candidates = list(_extract_json_candidates("结果 [1, 2, 3] 完成"))
        assert "[1, 2, 3]" in candidates

    def test_empty_input_yields_nothing(self):
        assert list(_extract_json_candidates("   ")) == []


class TestBuildGenerationPrompt:
    def _context(self, **overrides):
        context = {
            "requirement_content": "用户可用手机号登录并查看订单列表",
            "test_points": [
                {"module": "登录", "function": "短信登录", "point": "验证码正确可登录", "priority": 1},
                {"module": "订单", "function": "列表", "point": "可查看订单", "priority": 2},
            ],
            "ui_specs": [],
            "ui_description": "",
            "project_config": {"project_name": "演示项目"},
            "history_cases": [],
            "extra_requirements": "",
        }
        context.update(overrides)
        return context

    def test_min_case_count_三_when_two_test_points(self):
        prompt, min_count = _build_generation_prompt(self._context())
        assert min_count == 3
        assert "验证码正确可登录" in prompt

    def test_min_case_count_one_without_test_points(self):
        _, min_count = _build_generation_prompt(self._context(test_points=[]))
        assert min_count == 1

    def test_missing_ui_placeholder(self):
        prompt, _ = _build_generation_prompt(self._context())
        assert "无UI原型图解析结果" in prompt

    def test_history_cases_rendered(self):
        prompt, _ = _build_generation_prompt(
            self._context(history_cases=[{"id": 7, "title": "已有用例", "module": "登录", "summary": "摘要"}])
        )
        assert "项目已有测试用例" in prompt
        assert "[登录] 已有用例 (ID:7) — 摘要" in prompt

    def test_history_case_falls_back_to_expected_result(self):
        prompt, _ = _build_generation_prompt(
            self._context(history_cases=[{"id": 1, "title": "T", "module": "M", "expected_result": "预期"}])
        )
        assert "— 预期" in prompt

    def test_extra_requirements_section(self):
        prompt, _ = _build_generation_prompt(self._context(extra_requirements="仅生成正向用例"))
        assert "## 补充生成要求" in prompt
        assert "仅生成正向用例" in prompt

    def test_no_extra_requirements_section_when_empty(self):
        prompt, _ = _build_generation_prompt(self._context())
        assert "## 补充生成要求" not in prompt

    def test_non_dict_project_config_tolerated(self):
        prompt, _ = _build_generation_prompt(self._context(project_config="not-a-dict"))
        assert "无UI原型图解析结果" in prompt
