import json
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.pipelines.context import PipelineContext
from app.pipelines.steps._parsing import _parse_case_response

_TYPE_KEYWORDS = {
    "positive": ["正向", "正常", "主流程", "happy", "成功提交", "完整流程", "正确输入", "常规"],
    "boundary": ["边界", "上限", "下限", "最大", "最小", "临界", "超长", "超限", "空值", "极值",
                 "最多", "最少", "最长", "最短", "极限", "范围", "阈值"],
    "negative": ["异常", "错误", "失败", "缺失", "拒绝", "无权限", "断网", "超时", "容错", "拦截",
                 "非法", "无效", "不存在", "未授权", "冲突", "重复", "exception"],
}


def _classify_case_type(case: Dict[str, Any]) -> Optional[str]:
    title = (case.get("title") or "").lower()

    cat = (case.get("case_category") or case.get("case_type") or "").lower()
    if "boundary" in cat or "边界" in cat:
        return "boundary"
    if "negative" in cat or "异常" in cat or "abnormal" in cat or "exception" in cat:
        return "negative"
    if "positive" in cat or "正向" in cat or "normal" in cat or "happy" in cat:
        return "positive"

    text = title
    for type_name, keywords in _TYPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return type_name

    steps = case.get("steps", [])
    if isinstance(steps, list):
        steps_text = ""
        for step in steps:
            if isinstance(step, dict):
                steps_text += (step.get("action", "") + " " + step.get("expected_result", "")).lower()
        if steps_text:
            for type_name, keywords in _TYPE_KEYWORDS.items():
                if any(kw in steps_text for kw in keywords):
                    return type_name

    return "positive"


def _check_type_coverage(cases: List[Dict[str, Any]]) -> List[str]:
    covered = set()
    for case in cases:
        case_type = _classify_case_type(case)
        if case_type:
            covered.add(case_type)

    required = {"positive", "boundary", "negative"}
    return sorted(required - covered)


_SUPPLEMENT_EXAMPLES: Dict[str, Tuple] = {
    "positive": ("对比1-主流程", [
        "❌差劲：测试拍照提交作文功能 | 前置：账号已登录，APP运行正常 | 预期：页面正常→提交成功",
        "问题：描述笼统；前置缺网络/权限；预期模糊无判定标准",
        "✅优秀：联网+已授权验证拍照裁剪提交完整流程 | 前置：已登录、相机权限允许、设备网络正常 "
        "| 步骤：1.进入模块 2.拍摄裁剪 3.点击提交 "
        "| 预期：1.页面加载正常 2.相机唤起裁剪完成 3.提交成功跳转报告页",
        "优点：前置完整可复现；步骤原子化；预期与步骤一一对应",
    ]),
    "boundary": ("对比2-边界值", [
        "❌差劲：测试拍照数量限制 | 步骤：连续拍摄多张照片 | 预期：达到上限后禁止拍照",
        "问题：未量化上限；步骤模糊；预期缺弹窗文案校验",
        "✅优秀：验证最多3页拍摄限制 | 步骤：1.进拍摄页 2.依次拍3张 3.尝试拍第4张 "
        "| 预期：1.预览正常 2.3张保存成功 3.弹出上限提示无法触发第四次拍摄",
        "优点：精准覆盖边界值；操作量化复现性强；预期多重校验",
    ]),
    "negative": ("对比3-异常场景", [
        "❌差劲：无相机权限测试拍照 | 前置：相机权限禁止 | 预期：无法打开相机弹出提示",
        "问题：未区分临时/永久拒绝；预期过于简单未校验弹窗按钮",
        "✅优秀：相机权限永久拒绝 | 前置：已登录、系统关闭相机权限 "
        "| 步骤：1.点击拍照入口 "
        "| 预期：1.无法唤起相机弹出权限引导弹窗，弹窗含提示文案、取消、前往设置按钮",
        "优点：精准锁定异常场景；校验弹窗文案+按钮+跳转逻辑",
    ]),
}


def _append_supplement_examples(parts: List[str], missing_types: List[str]) -> None:
    priority_order = ["negative", "boundary", "positive"]
    selected = [t for t in priority_order if t in missing_types][:2]

    if not selected:
        return

    parts.append("## 正反用例对比（学习优秀写法，避免差劲写法）")
    parts.append("")
    for miss_type in selected:
        entry = _SUPPLEMENT_EXAMPLES.get(miss_type)
        if entry is None:
            continue
        title, lines = entry
        parts.append(f"【{title}】")
        parts.extend(lines)
        parts.append("")


def _generate_supplemental(
    ctx: PipelineContext,
    tp: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    missing_types: List[str],
    existing_titles: List[str],
    has_ui: bool,
) -> Optional[List[Dict[str, Any]]]:
    type_labels = {
        "positive": "正向用例（Happy Path）",
        "boundary": "边界值用例",
        "negative": "异常用例",
    }
    missing_labels = [type_labels.get(t, t) for t in missing_types]
    existing_titles_text = "、".join(f"「{t}」" for t in existing_titles[:10])

    parts: List[str] = []

    parts.append("你是一名资深测试工程师。")
    parts.append("")

    parts.append("## 任务")
    parts.append("以下测试点已生成部分用例，但缺少以下测试类型：")
    for label in missing_labels:
        parts.append(f"- {label}")
    parts.append("请为该测试点补充生成缺失类型的测试用例，每种缺失类型至少1条。")
    parts.append("")
    parts.append(f"已有用例标题（禁止重复）：{existing_titles_text or '无'}")
    parts.append("")

    parts.append("## 测试点信息")
    parts.append(json.dumps(tp, ensure_ascii=False))
    parts.append("")

    parts.append("## 生成规则")
    if "positive" in missing_types:
        parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
        parts.append("2. 分支流程需标注触发条件，作为独立场景生成用例")
    if "negative" in missing_types:
        parts.append("3. 异常流程需标注异常场景和预期错误提示")
    if "boundary" in missing_types:
        parts.append("4. 边界值用例需量化上下限，预期含界面+数据+弹窗多重校验")
    parts.append(
        "5. 标题格式：「场景/条件」+「操作」+「验证重点」，8-50字，"
        "禁用\"功能验证\"等模糊词"
    )
    parts.append(
        "6. 前置条件必须含\"账号已登录\"和网络环境，"
        "禁止依赖特定业务数据，禁止含操作步骤或页面导航状态"
    )
    parts.append(
        "7. 步骤原子化可执行，每步必须有 action 和 expected_result，禁止口语化"
    )
    parts.append(
        "8. 预期结果可量化判定，禁止\"页面正常\"\"功能正常\"等模糊描述"
    )
    parts.append(
        "9. 步骤数量约束：每条用例2-8步；正向用例通常3-8步，边界和异常用例通常2-5步；"
        "超过8步说明混合了多个测试场景，必须拆分为多条独立用例"
    )
    parts.append("")

    _append_supplement_examples(parts, missing_types)

    parts.append("## 输出格式要求：")
    parts.append("严格按以下JSON数组格式输出，不要添加任何其他文字：")
    parts.append("")
    parts.append("[")
    parts.append("  {")
    parts.append('    "title": "用例标题（8-50字，要素明确，禁止模糊词）",')
    parts.append('    "module": "所属模块",')
    parts.append('    "precondition": "前置条件（含登录状态、网络环境）",')
    parts.append('    "steps": [')
    parts.append('      {"step": "1", "description": "步骤描述", "action": "具体操作步骤", "action_type": "click/input/navigate", "input_value": "输入值", "target_element": "目标元素", "expected_result": "每步预期结果"}')
    parts.append('    ],')
    parts.append('    "expected_result": "整体预期结果",')
    parts.append('    "case_type": "ui_automation/manual/api_automation",')
    parts.append('    "priority": 数字1-5,')
    parts.append('    "case_category": "positive/boundary/exception",')
    parts.append('    "test_data": {},')
    parts.append('    "depends_on": "null或所依赖的主干用例标题",')
    parts.append('    "anchor_step": "null或所依赖的主干用例步骤号"')
    parts.append('  }')
    parts.append(']')

    supplement_prompt = "\n".join(parts)

    try:
        response = ctx.get_ai_client().complete(
            prompt=supplement_prompt,
            temperature=0.4,
            max_tokens=3000,
            metadata={
                "step_name": "case_generation_supplement",
                "test_point_id": tp.get("id"),
                "iteration_id": ctx.iteration_id,
                "supplement_for_types": ",".join(missing_types),
            },
        )
        if not response.content:
            return None
        return _parse_case_response(response.content)
    except Exception as e:
        logger.warning("追加生成失败 tp_id={}: {}", tp.get("id"), e)
        return None
