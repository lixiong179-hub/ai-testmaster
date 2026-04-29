"""XMind AI 增强解析器。

使用 LLM 将 XMind 路径批量转换为结构化测试用例。
对每批路径调用一次 AI，返回与 XmindCaseParser 兼容的 dict 列表。

依赖:
    - openai: OpenAI 兼容 SDK（DeepSeek）
    - app.core.config.settings: API 密钥与模型配置
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from openai import OpenAI

from app.core.config import settings
from app.services.xmind_case_parser import XmindCaseParser
from app.utils.ai_client_core import AITimeoutError, _detect_ai_error

# 缺省值：当未传入构造参数且 settings 中未配置时回退使用
BATCH_SIZE = 10
DEFAULT_AI_TIMEOUT = 90
DEFAULT_MAX_WORKERS = 4
DEFAULT_MAX_TOKENS = 8192

SYSTEM_PROMPT = """\
你是一名资深测试工程师，擅长将思维导图路径转换为结构化测试用例。

输入格式：每行一条路径，节点之间用 " → " 分隔。
第一个节点是模块名，后续节点组成测试场景。

你的任务：
1. 识别 **前置条件** —— 仅描述环境与权限状态（如"账号已登录""设备网络正常"），禁止包含业务数据和导航状态
2. 识别 **操作步骤** —— 用户执行的动作（如"点击XX""选择XX""输入XX"），必须包含完整导航路径
3. 识别 **中间预期** —— 系统对某步骤的响应（如"弹出提示框""界面显示XX"）
4. 识别 **最终预期结果** —— 通常是路径最后一个节点描述的结果，必须有具体判定标准
5. 生成具体的 **用例标题**（≤50字），格式：「场景/条件」+「操作」+「验证重点」，如"未选单词时纸张听写按钮置灰不可点击"，禁止"功能验证""界面测试"等模糊词

输出 JSON 对象，每个元素对应一条输入路径，字段：
{
  "module": "模块名",
  "precondition": "前置条件1\\n前置条件2",
  "title": "场景+操作+验证重点",
  "steps": [
    {"action": "操作描述", "expected_result": "该步预期（可为空）"}
  ],
  "expected_result": "最终预期结果",
  "priority": 2
}

规则：
- steps 中每个 action 必须是用户主动操作；系统响应放在上一步的 expected_result 中
- **优先级合理分配**：不要全部设为2！核心业务流程（如听写提交、数据保存）设为1（高）；一般功能入口和UI校验设为2（中）；边缘辅助场景设为3（低）。路径中出现"核心""必须""关键"等设为1，出现"可选""低优"设为3
- precondition 不能包含操作步骤或预期结果；必须完整注明网络状态、权限等必要环境
- **前置条件强制补充**：即使XMind路径未提及，precondition必须包含"账号已登录"和网络环境（Web端写"浏览器网络正常"，App端写"设备网络正常"），有权限相关场景必须补充权限状态（如"相机权限已开启"）
- **前置条件不依赖业务数据**：前置条件只约束环境与权限，禁止依赖特定业务数据（如"列表有数据""数据较多""已有听写记录数据""已选择有教材内容的教材"），确保用例任意环境可独立执行；如需特定数据才能测试（如编辑/删除场景），应在步骤中先创建数据，而非在前置中假设数据已存在
- **前置条件不含操作步骤和导航状态**：前置条件不能包含操作步骤或页面导航状态（如"已进入详情页""在列表页面""已进入听写状态""已选择教材"），导航到达目标页面必须作为步骤体现，确保用例可独立自动化执行
- **标题禁止模糊**：禁止"验证场景""界面校验""功能验证"等无校验目标的标题，必须写明具体验证什么（如"未选汉字时纸张听写按钮置灰不可点击"）
- **禁止纯操作步骤作为标题**：标题不能只写"进入XX页面""点击XX按钮"，必须附带验证目标（如"进入字词听写页面后验证教材列表和功能按钮完整展示"）
- 如果路径只有状态描述没有操作步骤，必须根据上下文推断用户会看到什么、校验什么，生成具体的验证操作（如"查看页面按钮状态""检查列表展示"），禁止使用"验证场景"等模糊词
- expected_result 必须有具体判定标准，禁止"提交成功""正常显示"等模糊描述；必须包含交互校验点如弹窗文案、按钮跳转
- **自动化友好**：步骤和预期必须支持自动化断言，预期需有可量化判定标准（如"无白屏""按钮置灰"），禁止"页面正常""功能正常"等无法断言的描述；步骤必须包含从登录后到达目标页面的完整导航操作，禁止将导航隐藏在前置条件中；弱网、异常条件等自动化无法实现的场景标注case_type为manual
- **同模块入口去重**：同一模块下如果多条路径都是"进入XX页面"类型的入口校验，每条case必须有不同的验证重点（如验证不同数据状态的展示、验证不同功能区域的渲染），禁止生成仅前置条件不同而验证目标相同的重复用例
- 输出格式必须是 JSON 对象：{"cases": [...]}
- cases 数量必须和输入路径数量一致
- 只输出 JSON，不要任何解释文字

## XMind路径解析正反示例（关键！必须严格参照）

以下示例展示了从XMind路径生成测试用例时，差劲写法和优秀写法的对比。你必须避免差劲写法中的所有问题。

【路径解析对比1-入口去重】
输入路径：
1. 字词听写 → 进入字词听写模块
2. 字词听写 → 进入字词听写页面
3. 字词听写 → 有教材内容 → 进入字词听写页面
4. 字词听写 → 无教材内容 → 进入字词听写页面

❌差劲输出（4条重复入口用例）：
路径1→ title:"进入字词听写模块", precondition:"账号已登录\n设备网络正常", priority:2
路径2→ title:"进入字词听写页面", precondition:"账号已登录\n设备网络正常", priority:2
路径3→ title:"进入字词听写页面", precondition:"账号已登录\n设备网络正常\n已选择有教材内容的教材", priority:2
路径4→ title:"进入字词听写页面", precondition:"账号已登录\n设备网络正常\n无教材内容", priority:2
问题：4条用例测试价值重复，都是"进入页面"；前置条件含业务数据"已选择有教材内容的教材"；标题无验证目标只写操作；优先级全2无区分

✅优秀输出（4条路径各生成有区分度的用例）：
路径1→ title:"进入字词听写模块后验证页面功能入口与教材列表完整展示", precondition:"账号已登录\n设备网络正常", steps:[{"action":"点击进入字词听写模块","expected_result":"页面加载完成无白屏无报错"},{"action":"检查页面功能入口和教材列表展示","expected_result":"教材列表正常展示功能按钮完整可见"}], priority:2
路径2→ title:"进入字词听写页面后验证听写记录列表展示状态", precondition:"账号已登录\n设备网络正常", steps:[{"action":"点击进入字词听写模块","expected_result":"页面加载完成"},{"action":"完成一次听写并提交","expected_result":"提交成功听写记录已生成"},{"action":"进入听写记录页面检查列表","expected_result":"记录列表展示听写得分详情完整"}], priority:2
路径3→ title:"有教材内容时进入字词听写页面验证教材单元与字词数据正常加载", precondition:"账号已登录\n设备网络正常", steps:[{"action":"点击进入字词听写模块","expected_result":"页面加载完成"},{"action":"选择有教材内容的教材","expected_result":"教材下单元列表正常展示"},{"action":"选择单元查看字词数据","expected_result":"字词列表正常加载字词数量展示正确"}], priority:1
路径4→ title:"无教材内容时进入字词听写页面验证空状态提示展示", precondition:"账号已登录\n设备网络正常", steps:[{"action":"点击进入字词听写模块","expected_result":"页面加载完成"},{"action":"检查无教材时的页面展示","expected_result":"显示空状态提示文案引导用户添加教材"}], priority:2
优点：每条用例验证目标不同不重复；前置条件只含环境与权限；标题含验证目标；steps完整含action和expected_result；优先级有区分（核心路径=1）

【路径解析对比2-前置条件禁止导航状态】
输入路径：字词听写 → 已进入听写状态 → 点击暂停按钮

❌差劲输出：
title:"在听写进行中点击暂停按钮", precondition:"账号已登录\n设备网络正常\n已进入听写状态", priority:2
问题：前置条件含导航状态"已进入听写状态"，自动化无法直接执行

✅优秀输出：
title:"听写进行中点击暂停按钮验证音频暂停与恢复交互", precondition:"账号已登录\n设备网络正常", steps:1.导航至字词听写模块 2.选择教材和单元 3.点击开始听写 4.点击暂停按钮, priority:1
优点：前置条件只含环境；步骤包含完整导航路径；标题含验证目标；核心交互优先级=1

【路径解析对比3-前置条件禁止业务数据】
输入路径：字词听写 → 已有听写记录数据 → 进入听写记录页面

❌差劲输出：
title:"进入听写记录页面", precondition:"账号已登录\n设备网络正常\n已有听写记录数据", priority:2
问题：前置条件含业务数据"已有听写记录数据"；标题无验证目标

✅优秀输出：
title:"进入听写记录页面验证历史听写记录列表与得分详情展示", precondition:"账号已登录\n设备网络正常", steps:1.导航至字词听写模块 2.完成一次听写并提交 3.进入听写记录页面 4.检查记录列表, priority:2
优点：前置条件不含业务数据；步骤中先创建数据再验证；标题含验证目标

正反用例对比（学习优秀写法，避免差劲写法）：

【对比1-主流程】
❌差劲：测试拍照提交作文功能 | 前置：账号已登录，APP运行正常 | 步骤：进入页面→拍摄裁剪→点击提交 | 预期：页面正常→拍照正常→提交成功显示结果
问题：描述笼统无校验目标；前置条件缺网络/权限；步骤口语化；预期模糊无判定标准
✅优秀：联网+已授权，验证拍照裁剪提交完整流程 | 前置：账号已登录、相机权限允许、设备网络正常 | 步骤：1.点击进入中文作文批改模块 2.点击拍照拍摄作文并完成裁剪确认 3.点击去批改按钮提交图片 | 预期：1.模块页面加载正常功能入口完整 2.相机正常唤起图片裁剪完成并本地保存 3.提交请求正常发起成功跳转展示批改报告
优点：描述清晰目标明确；前置条件完整可稳定复现；步骤原子化；步骤与预期一一对应

【对比2-边界值】
❌差劲：测试拍照数量限制 | 前置：账号已登录 | 步骤：打开拍照页面→连续拍摄多张照片 | 预期：拍照页面正常→达到上限后禁止继续拍照
问题：未明确页数上限无量化标准；步骤模糊无固定复现路径；预期缺弹窗文案等校验点
✅优秀：验证最多3页拍摄限制，超出上限校验拦截提示 | 前置：账号已登录、相机权限开启、规则限制最多3页 | 步骤：1.进入作文拍照拍摄页面 2.依次拍摄并保存3张作文图片 3.再次点击拍摄按钮尝试拍摄第4页 | 预期：1.相机预览界面正常展示无闪退黑屏 2.3张图片全部保存成功底部预览栏正常展示 3.弹出页数上限提示无法触发第四次拍摄
优点：精准覆盖边界值；操作步骤量化复现性强；预期含界面+数据+弹窗多重校验

【对比3-异常场景】
❌差劲：无相机权限测试拍照 | 前置：相机权限禁止 | 步骤：点击进入拍照功能 | 预期：无法打开相机弹出提示
问题：未区分临时/永久拒绝场景覆盖不足；预期过于简单未校验弹窗按钮跳转
✅优秀：相机权限永久拒绝，校验权限拦截与引导弹窗 | 前置：账号已登录、系统关闭APP相机权限 | 步骤：1.点击中文作文批改拍照入口 | 预期：1.无法唤起相机预览自动弹出权限引导弹窗 2.弹窗包含提示文案、取消、前往设置按钮功能可用
优点：精准锁定异常场景；全量校验弹窗文案+按钮+跳转逻辑；预期具体可落地

【对比4-网络异常】
❌差劲：断网提交作文测试 | 前置：已拍好作文图片 | 步骤：关闭手机网络→点击提交批改 | 预期：网络关闭成功→提交失败提示网络错误
问题：未明确断网时机复现性差；预期缺加载状态重试等交互校验；未校验APP容错防崩溃
✅优秀：图片准备完成后断网，校验提交时网络异常处理 | 前置：账号已登录、已完成作文拍照保存 | 步骤：1.手动关闭WiFi与移动数据断开网络 2.点击去批改发起提交请求 | 预期：1.设备识别为无网络状态 2.请求终止弹出网络异常提示页面无卡死无长期加载
优点：场景贴近真实使用；兼顾功能校验与容错性；步骤和预期严格绑定

【对比5-引导弹窗】
❌差劲：测试关闭首页引导弹窗 | 前置：首次进入作文页面 | 步骤：等待弹窗出现→点击关闭按钮 | 预期：弹窗正常弹出→弹窗关闭页面正常使用
问题：前置条件不严谨无缓存限制说明；未校验UI文案样式；预期宽泛判定标准不一致
✅优秀：首次进入模块，验证引导弹窗展示关闭交互 | 前置：账号已登录、浏览器网络正常、系统功能访问权限正常 | 步骤：1.清除弹窗关闭缓存后进入中文作文批改首页 2.查看页面弹窗内容 3.点击弹窗关闭按钮 | 预期：1.页面加载完成后自动弹出新手引导弹窗 2.弹窗文案图片展示完整样式符合设计 3.弹窗正常关闭首页所有功能按钮可正常点击操作
优点：前置条件只约束环境与权限；步骤中处理缓存状态而非前置中假设；覆盖UI+文案+交互+联动多维度；标准统一适合团队协作

【对比6-Web端列表页】
❌差劲：测试版本列表页面加载 | 前置：账号已登录系统 | 步骤：1.点击左侧测试页面版本菜单 | 预期：1.页面可以正常打开没有报错
问题：前置缺浏览器/网络约束无法稳定复现；步骤单一无元素检查动作；预期模糊笼统无具体校验点无法做自动化断言；覆盖极低UI错乱元素缺失无法发现
✅优秀：验证测试页面版本列表页访问、元素及基础渲染展示 | 前置：账号已登录、浏览器网络正常、系统功能访问权限正常无弹窗遮罩阻挡 | 步骤：1.点击左侧导航栏「测试页面版本」菜单入口 2.等待页面全部资源加载完成 3.检查页面按钮、表格表头、分页控件展示状态 | 预期：1.菜单点击响应正常跳转至版本列表页面 2.页面无白屏无接口报错无样式错乱 3.核心功能按钮、表格列表、分页组件正常渲染展示
优点：前置只约束环境与权限不依赖业务数据任意环境可独立执行；步骤原子化动作清晰便于自动化元素定位；操作与预期逐条对应校验点明确可断言

【对比7-Web端交互闭环】
❌差劲：测试新建版本按钮功能 | 前置：进入版本管理列表页面 | 步骤：1.点击页面右上角新建版本按钮 | 预期：1.弹出新增窗口功能正常使用
问题：前置含操作步骤而非环境状态自动化无法直接执行；操作流程不完整只点击不校验弹窗关闭按钮状态；预期口语化无明确判定标准不支持自动化落地
✅优秀：验证新建版本按钮点击、弹窗弹出与取消关闭交互 | 前置：账号已登录、浏览器网络正常、系统功能访问权限正常 | 步骤：1.点击左侧导航栏「测试页面版本」菜单进入版本列表页面 2.点击页面右上角「新建版本」功能按钮 3.观察新增弹窗整体布局表单及操作按钮展示 4.点击弹窗取消按钮关闭新增弹窗 | 预期：1.菜单点击响应正常跳转至版本列表页面 2.按钮点击无延迟无重复触发交互响应正常 3.新增弹窗正常居中弹出页面布局控件展示无误 4.取消按钮可正常关闭弹窗列表页面原有状态保持不变
优点：步骤包含完整导航路径用例可独立自动化执行；全程仅操作前端控件无数据依赖用例完全解耦；交互流程完整闭环覆盖导航弹窗关闭全链路
"""


def _build_user_prompt(paths: List[List[str]]) -> str:
    """将多条路径拼成用户提示。"""
    lines = []
    for i, path in enumerate(paths, 1):
        lines.append(f"{i}. {' → '.join(path)}")
    return "\n".join(lines)


def _parse_ai_response(text: str, expected_count: int) -> Optional[List[Dict[str, Any]]]:
    """从 AI 响应中提取 JSON 数组。"""
    text = text.strip()
    if not text:
        logger.warning("AI 响应内容为空")
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r"[{\[].*[}\]]", text, re.DOTALL)
        if not json_match:
            logger.warning("AI 响应中未找到 JSON")
            return None
        json_text = json_match.group()
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as exc:
            repaired_text = _repair_json_text(json_text)
            try:
                parsed = json.loads(repaired_text)
            except json.JSONDecodeError as repaired_exc:
                logger.warning(f"AI 响应 JSON 解析失败: {repaired_exc}")
                partial_cases = _extract_case_objects(repaired_text)
                if not partial_cases:
                    return None
                parsed = partial_cases

    if isinstance(parsed, dict):
        for key in ("cases", "items", "data", "results"):
            if key in parsed and isinstance(parsed[key], list):
                parsed = parsed[key]
                break

    if not isinstance(parsed, list):
        logger.warning("AI 响应无法提取为数组")
        return None

    if len(parsed) != expected_count:
        logger.warning(
            f"AI 返回 {len(parsed)} 条，期望 {expected_count} 条"
        )

    return parsed


def _repair_json_text(text: str) -> str:
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    text = re.sub(r"}\s*{", "},{", text)
    text = re.sub(r"]\s*{", "],{", text)
    text = re.sub(r"}\s*\[", "},[", text)
    # 相邻 JSON 对象属性之间缺少逗号时补全。
    # 前提：JSON 标准不允许字符串值内出现裸换行符，所以 \n 一定是属性分隔。
    text = re.sub(r'([}\]"])\s*\n\s*("[^"\n]+"\s*:)', r"\1,\2", text)
    return text


def _extract_case_objects(text: str) -> List[Dict[str, Any]]:
    cases_match = re.search(r'"cases"\s*:\s*\[', text)
    if cases_match:
        start = cases_match.end()
        end = text.rfind("]")
        source = text[start:end if end > start else len(text)]
    else:
        array_start = text.find("[")
        array_end = text.rfind("]")
        if array_start == -1:
            source = text
        else:
            source = text[array_start + 1:array_end if array_end > array_start else len(text)]

    decoder = json.JSONDecoder()
    results: List[Dict[str, Any]] = []
    index = 0
    while index < len(source):
        object_start = source.find("{", index)
        if object_start == -1:
            break
        try:
            parsed, offset = decoder.raw_decode(source[object_start:])
        except json.JSONDecodeError:
            index = object_start + 1
            continue
        if isinstance(parsed, dict):
            results.append(parsed)
        index = object_start + offset
    return results


def _normalize_case(raw: Dict[str, Any], fallback_module: str) -> Dict[str, Any]:
    """将 AI 返回的单条数据规范化为 XmindCaseParser 兼容格式。"""
    module = raw.get("module", fallback_module) or fallback_module
    precondition = raw.get("precondition", "")
    title = raw.get("title", "")[:XmindCaseParser.TITLE_MAX_LEN]
    expected_result = raw.get("expected_result", "")
    priority = raw.get("priority", 2)
    if priority not in (1, 2, 3):
        priority = 2

    raw_steps = raw.get("steps", [])
    steps: List[Dict[str, Any]] = []
    for idx, step in enumerate(raw_steps, 1):
        if isinstance(step, dict):
            steps.append({
                "step": idx,
                "action": step.get("action", ""),
                "expected_result": step.get("expected_result", ""),
                "param": "",
            })

    if not steps and expected_result:
        steps = [{
            "step": 1,
            "action": f"检查并确认：{title}",
            "expected_result": expected_result,
            "param": "",
        }]

    actions = [s["action"] for s in steps if s["action"]]

    # 优先取title作为point（title含验证目标），仅当title为空时取第一个action
    point = title[:XmindCaseParser.POINT_MAX_LEN] if title else (actions[0][:XmindCaseParser.POINT_MAX_LEN] if actions else "")

    return {
        "module": module[:XmindCaseParser.MODULE_MAX_LEN],
        "function": "",
        "title": title,
        "point": point,
        "precondition": precondition,
        "steps": steps,
        "expected_result": expected_result,
        "priority": priority,
        "case_type": raw.get("case_type", "manual") or "manual",
        "source_depth": 0,
        "action_count": len(actions),
        "expected_count": 1 if expected_result else 0,
        "condition_count": len(precondition.split("\n")) if precondition else 0,
        "ignored_count": 0,
    }


class XmindAIParser:
    """使用 LLM 将 XMind 路径批量转换为测试用例。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        timeout: Optional[int] = None,
        max_workers: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.DEEPSEEK_API_KEY
        self._base_url = base_url if base_url is not None else "https://api.deepseek.com"
        self._model = model if model is not None else settings.DEEPSEEK_MODEL
        self._batch_size = (
            batch_size if batch_size is not None
            else getattr(settings, "XMIND_AI_BATCH_SIZE", BATCH_SIZE)
        )
        self._timeout = (
            timeout if timeout is not None
            else getattr(settings, "XMIND_AI_TIMEOUT", DEFAULT_AI_TIMEOUT)
        )
        self._max_workers = (
            max_workers if max_workers is not None
            else getattr(settings, "XMIND_AI_MAX_WORKERS", DEFAULT_MAX_WORKERS)
        )
        self._max_tokens = (
            max_tokens if max_tokens is not None
            else getattr(settings, "XMIND_AI_MAX_TOKENS", DEFAULT_MAX_TOKENS)
        )

        # 参数正值校验
        if self._batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {self._batch_size}")
        if self._timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self._timeout}")
        if self._max_workers <= 0:
            raise ValueError(f"max_workers must be positive, got {self._max_workers}")
        if self._max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self._max_tokens}")
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    def parse_paths(
        self,
        paths: List[List[str]],
        progress_callback: Optional[Callable[[int, int, int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """将多条路径通过 AI 转换为测试用例。

        Args:
            paths: 每条路径是字符串列表，如 ["字词听写", "有教材内容", "点击听写记录", ...]
            progress_callback: 进度回调函数，参数为
                (completed_batches, total_batches, completed_paths, total_paths)，
                每完成一个批次时调用。

        Returns:
            与 XmindCaseParser 兼容的 dict 列表。
        """
        if not paths:
            return []

        batches: List[tuple] = []
        for batch_start in range(0, len(paths), self._batch_size):
            batch = paths[batch_start : batch_start + self._batch_size]
            batches.append((batch_start, batch))

        worker_count = min(self._max_workers, len(batches))
        logger.info(
            f"AI 增强解析开始：{len(paths)} 条路径，{len(batches)} 批，"
            f"并发 {worker_count}，单批超时 {self._timeout}s"
        )

        overall_start = time.perf_counter()
        results_by_index: Dict[int, List[Dict[str, Any]]] = {}
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_meta = {
                executor.submit(self._call_ai, batch): (idx, batch_start, batch)
                for idx, (batch_start, batch) in enumerate(batches)
            }
            # 使用 as_completed 让早完成批次先进入处理与日志，提高观察性
            for future in as_completed(future_to_meta):
                idx, batch_start, batch = future_to_meta[future]
                try:
                    batch_results = future.result()
                except Exception as exc:  # noqa: BLE001
                    # 防御性兜底：_call_ai 内部已捕获所有异常并返回 None，
                    # 这里仅防止未来重构时异常泄漏到调度层。
                    logger.error(
                        f"AI 批次 {batch_start}-{batch_start + len(batch)} "
                        f"线程异常: {exc}"
                    )
                    batch_results = None

                normalized: List[Dict[str, Any]] = []
                if batch_results is not None:
                    if len(batch_results) != len(batch):
                        logger.warning(
                            f"AI 批次 {batch_start}-{batch_start + len(batch)} "
                            f"返回 {len(batch_results)} 条，按可用结果导入"
                        )
                    for raw, path in zip(batch_results, batch):
                        fallback_module = path[0] if path else ""
                        normalized.append(_normalize_case(raw, fallback_module))
                else:
                    logger.warning(
                        f"AI 批次 {batch_start}-{batch_start + len(batch)} 失败，跳过"
                    )
                results_by_index[idx] = normalized

                # 进度回调
                if progress_callback:
                    completed_batches = len(results_by_index)
                    completed_paths = sum(
                        len(results_by_index.get(i, [])) for i in range(len(batches))
                    )
                    progress_callback(
                        completed_batches, len(batches), completed_paths, len(paths)
                    )

        # 按输入顺序合并结果，保证输出确定性
        all_results: List[Dict[str, Any]] = []
        for idx in range(len(batches)):
            all_results.extend(results_by_index.get(idx, []))

        elapsed = time.perf_counter() - overall_start
        logger.info(
            f"AI 增强解析完成，成功 {len(all_results)}/{len(paths)} 条，"
            f"总耗时 {elapsed:.1f}s"
        )
        return all_results

    def _call_ai(self, batch: List[List[str]]) -> Optional[List[Dict[str, Any]]]:
        """调用 LLM 处理一个批次。"""
        user_prompt = _build_user_prompt(batch)
        start = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
            )
            elapsed = time.perf_counter() - start
            content = response.choices[0].message.content or ""
            finish_reason = getattr(response.choices[0], "finish_reason", "")
            logger.debug(
                f"AI 批次返回：长度 {len(content)} 字符，耗时 {elapsed:.1f}s，"
                f"finish_reason={finish_reason}"
            )
            if not content.strip():
                logger.warning(
                    f"AI 响应内容为空，finish_reason={finish_reason}，耗时 {elapsed:.1f}s"
                )
                return None
            if finish_reason == "length":
                logger.warning(
                    "AI 响应被 max_tokens 截断，建议调大 XMIND_AI_MAX_TOKENS 或减小 XMIND_AI_BATCH_SIZE"
                )
            return _parse_ai_response(content, len(batch))
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            ai_error = _detect_ai_error(exc)
            if isinstance(ai_error, AITimeoutError):
                logger.warning(f"AI 调用超时（{self._timeout}秒），耗时 {elapsed:.1f}s: {exc}")
            else:
                logger.error(f"AI 调用失败，耗时 {elapsed:.1f}s: {exc}")
            return None
