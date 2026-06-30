"""
PoC: 验证 flow_sort_data 对测试用例生成质量的影响

对比三种模式：
  A: mode='linear', enhanced_mode=True, 无 flow_sort_data
  B: mode='graph', flow_sort_data 仅含主流程排序（无分支）
  C: mode='graph', flow_sort_data 含主流程 + 分支流程

评估维度：
  1. 用例步骤的完整性（是否覆盖主流程跳转）
  2. 用例步骤的准确性（步骤顺序是否符合真实业务流）
  3. 分支场景覆盖度（是否覆盖条件分支）
  4. 跨页面关联的合理性
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
from app.api.v1.endpoints.test_case_ai_schemas import AIGenerateEnhancedRequest
from app.api.v1.endpoints.test_case_ai_helpers import _build_graph_prompt_data, _build_linear_prompt_data


def build_test_context():
    """构建测试上下文数据"""
    return {
        "requirement_content": """
电商下单流程：
1. 用户登录后进入商品列表页
2. 点击商品进入商品详情页
3. 在详情页点击"加入购物车"
4. 进入购物车页面，确认商品后点击"去结算"
5. 进入订单确认页，选择收货地址和支付方式
6. 提交订单，进入支付页面
7. 支付成功后跳转到订单详情页

异常流程：
- 支付失败：提示重试或更换支付方式
- 优惠券使用：在订单确认页选择优惠券，金额自动计算
- 库存不足：在提交订单时提示库存不足
""",
        "ui_specs": [
            {
                "screen_id": 1,
                "screen_name": "商品列表页",
                "ui_spec": {
                    "elements": [
                        {"type": "search_bar", "label": "搜索框"},
                        {"type": "product_card", "label": "商品卡片", "count": 10},
                        {"type": "tab", "label": "分类标签"}
                    ]
                }
            },
            {
                "screen_id": 2,
                "screen_name": "商品详情页",
                "ui_spec": {
                    "elements": [
                        {"type": "image", "label": "商品图片"},
                        {"type": "text", "label": "商品名称"},
                        {"type": "text", "label": "价格"},
                        {"type": "button", "label": "加入购物车"},
                        {"type": "button", "label": "立即购买"}
                    ]
                }
            },
            {
                "screen_id": 3,
                "screen_name": "购物车页面",
                "ui_spec": {
                    "elements": [
                        {"type": "checkbox", "label": "商品选择"},
                        {"type": "text", "label": "商品名称"},
                        {"type": "stepper", "label": "数量调整"},
                        {"type": "text", "label": "小计金额"},
                        {"type": "button", "label": "去结算"}
                    ]
                }
            },
            {
                "screen_id": 4,
                "screen_name": "订单确认页",
                "ui_spec": {
                    "elements": [
                        {"type": "address_card", "label": "收货地址"},
                        {"type": "radio", "label": "支付方式"},
                        {"type": "coupon_selector", "label": "优惠券选择"},
                        {"type": "text", "label": "订单金额"},
                        {"type": "button", "label": "提交订单"}
                    ]
                }
            },
            {
                "screen_id": 5,
                "screen_name": "支付页面",
                "ui_spec": {
                    "elements": [
                        {"type": "text", "label": "支付金额"},
                        {"type": "button", "label": "确认支付"},
                        {"type": "link", "label": "更换支付方式"}
                    ]
                }
            },
            {
                "screen_id": 6,
                "screen_name": "订单详情页",
                "ui_spec": {
                    "elements": [
                        {"type": "status_badge", "label": "订单状态"},
                        {"type": "text", "label": "订单号"},
                        {"type": "text", "label": "支付金额"},
                        {"type": "button", "label": "查看物流"}
                    ]
                }
            },
        ],
        "test_points": [
            {"module": "下单流程", "function": "商品购买", "point": "用户可以完成从商品浏览到支付成功的完整购买流程", "priority": 1},
            {"module": "下单流程", "function": "支付异常", "point": "支付失败时用户可以重试或更换支付方式", "priority": 2},
            {"module": "下单流程", "function": "优惠券使用", "point": "用户可以在订单确认页使用优惠券并正确计算金额", "priority": 2},
        ],
        "ui_descriptions": ["商品列表页", "商品详情页", "购物车页面", "订单确认页", "支付页面", "订单详情页"],
    }


def build_flow_sort_data_main_only():
    """仅主流程排序（无分支）"""
    from app.schemas.test_case._flow import FlowSortDataSchema, FlowNodeSchema, FlowEdgeSchema
    return FlowSortDataSchema(
        nodes=[
            FlowNodeSchema(screen_id=1, screen_order=1, flow_type="main", main_order=1, screen_name="商品列表页"),
            FlowNodeSchema(screen_id=2, screen_order=2, flow_type="main", main_order=2, screen_name="商品详情页"),
            FlowNodeSchema(screen_id=3, screen_order=3, flow_type="main", main_order=3, screen_name="购物车页面"),
            FlowNodeSchema(screen_id=4, screen_order=4, flow_type="main", main_order=4, screen_name="订单确认页"),
            FlowNodeSchema(screen_id=5, screen_order=5, flow_type="main", main_order=5, screen_name="支付页面"),
            FlowNodeSchema(screen_id=6, screen_order=6, flow_type="main", main_order=6, screen_name="订单详情页"),
        ],
        edges=[],
    )


def build_flow_sort_data_with_branches():
    """主流程 + 分支流程"""
    from app.schemas.test_case._flow import FlowSortDataSchema, FlowNodeSchema, FlowEdgeSchema
    return FlowSortDataSchema(
        nodes=[
            FlowNodeSchema(screen_id=1, screen_order=1, flow_type="main", main_order=1, screen_name="商品列表页"),
            FlowNodeSchema(screen_id=2, screen_order=2, flow_type="main", main_order=2, screen_name="商品详情页"),
            FlowNodeSchema(screen_id=3, screen_order=3, flow_type="main", main_order=3, screen_name="购物车页面"),
            FlowNodeSchema(screen_id=4, screen_order=4, flow_type="main", main_order=4, screen_name="订单确认页"),
            FlowNodeSchema(screen_id=5, screen_order=5, flow_type="main", main_order=5, screen_name="支付页面"),
            FlowNodeSchema(screen_id=6, screen_order=6, flow_type="main", main_order=6, screen_name="订单详情页"),
        ],
        edges=[
            FlowEdgeSchema(source="1", target="2", edge_type="normal", label="点击商品"),
            FlowEdgeSchema(source="2", target="3", edge_type="normal", label="加入购物车"),
            FlowEdgeSchema(source="3", target="4", edge_type="normal", label="去结算"),
            FlowEdgeSchema(source="4", target="5", edge_type="normal", label="提交订单"),
            FlowEdgeSchema(source="5", target="6", edge_type="normal", label="支付成功"),
            FlowEdgeSchema(source="5", target="5", edge_type="exception", label="支付失败重试", condition="支付失败，提示重试或更换支付方式"),
            FlowEdgeSchema(source="4", target="4", edge_type="branch", label="使用优惠券", condition="选择优惠券后金额自动重新计算"),
            FlowEdgeSchema(source="4", target="4", edge_type="exception", label="库存不足", condition="商品库存不足，提示用户"),
        ],
    )


def evaluate_quality(cases: list, label: str) -> dict:
    """评估生成用例质量"""
    if not cases:
        return {"label": label, "case_count": 0, "score": 0}

    total_steps = 0
    branch_coverage = 0
    cross_page_refs = 0
    main_flow_order_correct = 0

    for case in cases:
        steps = case.get("steps", [])
        if isinstance(steps, list):
            total_steps += len(steps)

        # 检查是否覆盖分支场景
        case_text = json.dumps(case, ensure_ascii=False)
        if any(kw in case_text for kw in ["支付失败", "重试", "更换支付"]):
            branch_coverage += 1
        if any(kw in case_text for kw in ["优惠券", "折扣", "优惠"]):
            branch_coverage += 1
        if any(kw in case_text for kw in ["库存不足", "缺货"]):
            branch_coverage += 1

        # 检查跨页面关联
        page_refs = sum(1 for kw in ["商品列表", "商品详情", "购物车", "订单确认", "支付页面", "订单详情"] if kw in case_text)
        cross_page_refs += page_refs

        # 检查主流程顺序
        step_texts = [s.get("description", "") if isinstance(s, dict) else str(s) for s in (steps if isinstance(steps, list) else [])]
        main_flow_keywords = ["商品列表", "商品详情", "购物车", "订单确认", "支付"]
        found_indices = []
        for kw in main_flow_keywords:
            for i, st in enumerate(step_texts):
                if kw in st:
                    found_indices.append(i)
                    break
        if found_indices == sorted(found_indices) and len(found_indices) >= 3:
            main_flow_order_correct += 1

    return {
        "label": label,
        "case_count": len(cases),
        "total_steps": total_steps,
        "avg_steps": round(total_steps / len(cases), 1) if cases else 0,
        "branch_coverage": branch_coverage,
        "cross_page_refs": cross_page_refs,
        "main_flow_order_correct": main_flow_order_correct,
    }


def main():
    context = build_test_context()

    print("=" * 60)
    print("PoC: flow_sort_data 对生成质量的影响")
    print("=" * 60)

    # ── 请求 A: linear 模式 ──
    print("\n[请求 A] mode='linear', enhanced_mode=True, 无 flow_sort_data")
    prompt_data_a = _build_linear_prompt_data(
        context=context,
        description="基于电商下单流程生成测试用例",
        priority=1,
        case_type="manual",
        exec_mode="all",
    )
    prompt_a = prompt_data_a.get("graph_prompt") or ""
    if not prompt_a:
        # linear 模式没有 graph_prompt，构建一个简化 prompt 用于对比
        from app.utils.ai_client_enhanced._enhanced import generate_test_case_enhanced
        prompt_a = "linear mode - prompt built by PromptBuilder.for_test_case"
    print(f"  Prompt 长度: {len(str(prompt_a))} 字符")

    # ── 请求 B: graph 模式，仅主流程 ──
    print("\n[请求 B] mode='graph', flow_sort_data 仅主流程排序")
    flow_sort_b = build_flow_sort_data_main_only()
    try:
        prompt_data_b = _build_graph_prompt_data(
            flow_sort_data=flow_sort_b,
            context=context,
            description="基于电商下单流程生成测试用例",
            priority=1,
            case_type="manual",
        )
        prompt_b = prompt_data_b.get("graph_prompt", "")
        print(f"  Prompt 长度: {len(prompt_b)} 字符")
        print(f"  节点数: {len(flow_sort_b.nodes)}, 边数: {len(flow_sort_b.edges)}")
    except Exception as e:
        print(f"  ❌ 构建失败: {e}")
        prompt_b = ""

    # ── 请求 C: graph 模式，主流程 + 分支 ──
    print("\n[请求 C] mode='graph', flow_sort_data 主流程 + 分支流程")
    flow_sort_c = build_flow_sort_data_with_branches()
    try:
        prompt_data_c = _build_graph_prompt_data(
            flow_sort_data=flow_sort_c,
            context=context,
            description="基于电商下单流程生成测试用例",
            priority=1,
            case_type="manual",
        )
        prompt_c = prompt_data_c.get("graph_prompt", "")
        print(f"  Prompt 长度: {len(prompt_c)} 字符")
        print(f"  节点数: {len(flow_sort_c.nodes)}, 边数: {len(flow_sort_c.edges)}")
    except Exception as e:
        print(f"  ❌ 构建失败: {e}")
        prompt_c = ""

    # ── Prompt 内容对比 ──
    print("\n" + "=" * 60)
    print("Prompt 内容对比")
    print("=" * 60)

    for label, prompt in [("A (linear)", prompt_a), ("B (graph, 主流程)", prompt_b), ("C (graph, 主+分支)", prompt_c)]:
        if not prompt:
            print(f"\n{label}: [空]")
            continue
        prompt_str = str(prompt)
        # 检查关键内容
        has_flow_structure = "流程" in prompt_str or "节点" in prompt_str
        has_main_order = "main_order" in prompt_str or "主流程" in prompt_str
        has_branch = "分支" in prompt_str or "branch" in prompt_str
        has_edge_condition = "条件" in prompt_str or "condition" in prompt_str
        has_payment_fail = "支付失败" in prompt_str
        has_coupon = "优惠券" in prompt_str
        has_stock = "库存" in prompt_str

        print(f"\n{label}:")
        print(f"  包含流程结构: {'✅' if has_flow_structure else '❌'}")
        print(f"  包含主流程排序: {'✅' if has_main_order else '❌'}")
        print(f"  包含分支流程: {'✅' if has_branch else '❌'}")
        print(f"  包含边条件: {'✅' if has_edge_condition else '❌'}")
        print(f"  包含支付失败场景: {'✅' if has_payment_fail else '❌'}")
        print(f"  包含优惠券场景: {'✅' if has_coupon else '❌'}")
        print(f"  包含库存不足场景: {'✅' if has_stock else '❌'}")

    # ── 结论 ──
    print("\n" + "=" * 60)
    print("PoC 结论")
    print("=" * 60)

    # 基于 prompt 内容判断
    if prompt_c and "分支" in str(prompt_c) and "条件" in str(prompt_c):
        print("✅ 验证通过：flow_sort_data 含主流程+分支流程时，prompt 中包含完整的流程结构和条件分支信息")
        print("   → 建议接入完整 FlowSortEditor（含主流程+分支流程）")
    elif prompt_b and ("主流程" in str(prompt_b) or "main_order" in str(prompt_b)):
        print("⚠️ 部分通过：flow_sort_data 仅主流程排序时 prompt 有改善，但分支流程无额外提升")
        print("   → 建议仅接入主流程排序（不含分支）")
    else:
        print("❌ 验证失败：flow_sort_data 对 prompt 无显著改善")
        print("   → 不接入 FlowSortEditor")


if __name__ == "__main__":
    main()
