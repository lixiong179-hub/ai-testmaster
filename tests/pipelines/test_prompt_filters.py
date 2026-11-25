"""PRD / UI 规格裁剪行为护栏（G-8 B5c：`_filter_*_by_testpoint` 拆分前置测试）。

两条纯函数路径直接影响生成 Prompt 的上下文预算，这里锁定：
    - `_filter_prd_by_testpoint`：空/短文本直通、无关键词截断、关键词段落排序取用、
      截断上限与原文顺序还原
    - `_filter_ui_specs_by_testpoint`：≤10 直通、无关键词取前 10、关键词命中优先、
      ui_spec 的 purpose / regions 参与匹配、非 dict 规格仅用 screen_name

注：既有 `tests/pipelines/test_prompt_builder*.py` 未覆盖这两条裁剪分支。
"""

from app.pipelines.steps._prompt import (
    _PRD_MAX_CHARS,
    _filter_prd_by_testpoint,
    _filter_ui_specs_by_testpoint,
)


class TestFilterPrd:
    def test_empty_content_passthrough(self):
        assert _filter_prd_by_testpoint("", {"module": "订单"}) == ""
        assert _filter_prd_by_testpoint("   \n  ", {"module": "订单"}) == "   \n  "

    def test_short_content_passthrough(self):
        content = "短需求文档"
        assert _filter_prd_by_testpoint(content, {"module": "订单"}) == content

    def test_long_content_without_keywords_truncated(self):
        content = "无关键字段落。" * (_PRD_MAX_CHARS // 7 + 20)
        result = _filter_prd_by_testpoint(content, {})
        assert result == content[:_PRD_MAX_CHARS]

    def test_short_keyword_parts_ignored(self):
        """单字关键词不参与匹配（长度 < 2）。"""
        content = "X" * (_PRD_MAX_CHARS + 100)
        result = _filter_prd_by_testpoint(content, {"module": "X"})
        assert result == content[:_PRD_MAX_CHARS]

    def test_matched_paragraph_kept_whole(self):
        """命中段落整段保留，其余段落按剩余预算切片。"""
        filler = "无关段落内容。" * 1000
        related = "订单模块：创建订单流程说明。"
        content = "\n\n".join([filler, related])

        result = _filter_prd_by_testpoint(content, {"module": "订单模块"})

        assert related in result
        assert len(result) < len(content)

    def test_total_selection_bounded_by_soft_cap(self):
        """字符预算按段落长度累加（不含拼接分隔符），输出略超上限属既有软上限。"""
        parts = [f"订单段落{i}：" + "内容" * 400 for i in range(10)]
        content = "\n\n".join(parts)

        result = _filter_prd_by_testpoint(content, {"module": "订单段落"})

        assert len(result) <= _PRD_MAX_CHARS + 2 * len(parts)

    def test_split_fields_all_contribute_keywords(self):
        """module / function / point 三段关键词都参与匹配（缺一段则对应段落被挤出预算）。"""
        filler = "无关内容。" * 1400
        by_module = "支付模块说明。"
        by_function = "退款流程说明。"
        by_point = "订单详情规则。"
        content = "\n\n".join([filler, by_module, by_function, by_point])

        result = _filter_prd_by_testpoint(content, {"module": "支付模块", "function": "退款", "point": "订单详情"})

        assert by_module in result
        assert by_function in result
        assert by_point in result


class TestFilterUiSpecs:
    def _specs(self, count: int) -> list[dict]:
        return [{"screen_name": f"页面{i}", "ui_spec": {"purpose": "普通页面"}} for i in range(count)]

    def test_small_list_passthrough(self):
        specs = self._specs(10)
        assert _filter_ui_specs_by_testpoint(specs, {"module": "订单"}) is specs

    def test_empty_list_passthrough(self):
        assert _filter_ui_specs_by_testpoint([], {"module": "订单"}) == []

    def test_no_keywords_keeps_first_ten(self):
        specs = self._specs(15)
        result = _filter_ui_specs_by_testpoint(specs, {})
        assert result == specs[:10]

    def test_keyword_matched_specs_prioritised(self):
        specs = self._specs(15)
        specs[12] = {"screen_name": "订单详情页", "ui_spec": {"purpose": "展示订单"}}

        result = _filter_ui_specs_by_testpoint(specs, {"module": "订单"})

        assert result[0]["screen_name"] == "订单详情页"
        assert len(result) == 10

    def test_matched_fewer_than_ten_filled_with_unmatched(self):
        specs = self._specs(15)
        specs[14] = {"screen_name": "订单列表页", "ui_spec": {}}

        result = _filter_ui_specs_by_testpoint(specs, {"module": "订单"})

        assert len(result) == 10
        assert result[0]["screen_name"] == "订单列表页"
        assert result[1] is specs[0]

    def test_purpose_and_regions_participate_in_matching(self):
        specs = self._specs(12)
        specs[11] = {
            "screen_name": "任意页",
            "ui_spec": {"purpose": "承载结算", "regions": {"结算区": {"x": 0}}},
        }

        result = _filter_ui_specs_by_testpoint(specs, {"function": "结算区"})

        assert result[0]["screen_name"] == "任意页"

    def test_non_dict_ui_spec_uses_screen_name_only(self):
        specs = self._specs(12)
        specs[11] = {"screen_name": "优惠券页", "ui_spec": "字符串规格"}

        result = _filter_ui_specs_by_testpoint(specs, {"module": "优惠券"})

        assert result[0]["screen_name"] == "优惠券页"
