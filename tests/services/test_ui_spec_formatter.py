"""`prompt_builder.ui_spec_formatter` 的格式化输出契约测试。

该模块是 ai_prompt_builder / ai_prompt_mixin 的「唯一实现」，拆分 helper 后
需要锁定逐段输出与截断规则，避免 prompt 文本漂移。
"""

from app.services.prompt_builder.ui_spec_formatter import (
    format_ui_spec_for_prompt,
    format_ui_specs_list,
)


class TestFormatUiSpecForPrompt:
    def test_empty_spec_only_header(self):
        assert format_ui_spec_for_prompt("登录页", {}) == "【页面：登录页】"

    def test_purpose(self):
        result = format_ui_spec_for_prompt("登录页", {"purpose": "用户登录"})
        assert result == "【页面：登录页】\n页面功能：用户登录"

    def test_regions_dict_skips_empty_desc(self):
        ui_spec = {"regions": {"header": "顶部栏", "body": "", "footer": None}}
        result = format_ui_spec_for_prompt("列表页", ui_spec)
        assert result == "【页面：列表页】\n页面区域：\n  - header: 顶部栏"

    def test_regions_list_uses_desc_fallback(self):
        ui_spec = {
            "regions": [
                {"name": "列表", "desc": "记录列表"},
                {"name": "", "description": "无名称描述"},
                {"name": ""},
                "not-a-dict",
            ]
        }
        result = format_ui_spec_for_prompt("列表页", ui_spec)
        lines = result.split("\n")
        assert lines[0] == "【页面：列表页】"
        assert lines[1] == "页面区域："
        assert lines[2] == "  - 列表: 记录列表"
        assert lines[3] == "  - : 无名称描述"
        assert len(lines) == 4

    def test_elements_label_fallback_and_defaults(self):
        ui_spec = {
            "elements": [
                {"type": "button", "label": "保存"},
                {"semantic": "取消"},
                {"name": "输入框", "state": "disabled", "interactive": True, "description": "用户名字段"},
            ]
        }
        result = format_ui_spec_for_prompt("详情页", ui_spec)
        assert "页面元素（共3个）：" in result
        assert "  - [button] 保存 | 状态:normal | 可交互:False | " in result
        assert "  - [未知] 取消 | 状态:normal | 可交互:False | " in result
        assert "  - [未知] 输入框 | 状态:disabled | 可交互:True | 用户名字段" in result

    def test_elements_truncated_to_30(self):
        ui_spec = {"elements": [{"type": str(i)} for i in range(40)]}
        result = format_ui_spec_for_prompt("详情页", ui_spec)
        assert "页面元素（共40个）：" in result
        assert result.count("  - [") == 30

    def test_navigation_skips_empty_values(self):
        ui_spec = {"navigation": {"top": "顶部导航", "left": "", "right": "侧栏"}}
        result = format_ui_spec_for_prompt("导航页", ui_spec)
        assert result == "【页面：导航页】\n导航结构：\n  - top: 顶部导航\n  - right: 侧栏"

    def test_layout_constraints_truncated_to_10(self):
        ui_spec = {"layout_constraints": [{"description": f"约束{i}"} for i in range(15)] + [{"desc": "无描述"}]}
        result = format_ui_spec_for_prompt("约束页", ui_spec)
        assert "布局约束（共16项）：" in result
        assert result.count("  - 约束") == 10
        assert "无描述" not in result

    def test_flows_expected_next_screens(self):
        ui_spec = {"flows": {"expected_next_screens": ["A", "B"]}}
        result = format_ui_spec_for_prompt("流程页", ui_spec)
        assert result == "【页面：流程页】\n预期跳转页面：A, B"

    def test_flows_without_next_screens_emits_nothing(self):
        assert format_ui_spec_for_prompt("流程页", {"flows": {}}) == "【页面：流程页】"
        assert format_ui_spec_for_prompt("流程页", {"flows": {"expected_next_screens": []}}) == "【页面：流程页】"

    def test_all_sections_ordered(self):
        ui_spec = {
            "purpose": "综合",
            "regions": {"a": "1"},
            "elements": [{"type": "input", "label": "x"}],
            "navigation": {"n": "v"},
            "layout_constraints": [{"description": "d"}],
            "flows": {"expected_next_screens": ["B"]},
        }
        result = format_ui_spec_for_prompt("全量页", ui_spec)
        assert result.split("\n") == [
            "【页面：全量页】",
            "页面功能：综合",
            "页面区域：",
            "  - a: 1",
            "页面元素（共1个）：",
            "  - [input] x | 状态:normal | 可交互:False | ",
            "导航结构：",
            "  - n: v",
            "布局约束（共1项）：",
            "  - d",
            "预期跳转页面：B",
        ]


class TestFormatUiSpecsList:
    def test_empty_list(self):
        assert format_ui_specs_list([]) == ""

    def test_multiple_specs_joined_by_blank_line(self):
        result = format_ui_specs_list(
            [
                {"screen_name": "首页", "ui_spec": {"purpose": "P1"}},
                {"screen_name": "详情", "ui_spec": {"purpose": "P2"}},
            ]
        )
        assert result == "【页面：首页】\n页面功能：P1\n\n【页面：详情】\n页面功能：P2"

    def test_skips_item_without_spec(self):
        result = format_ui_specs_list([{"screen_name": "空页", "ui_spec": {}}])
        assert result == ""
