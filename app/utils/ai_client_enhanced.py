import requests
import json
import re
import time
from typing import Dict, Any, Optional, List
from loguru import logger

from app.utils.ai_client_core import (
    AIServiceError,
    AIResponseParseError,
    AIResponseFormatError,
    _detect_ai_error,
    get_ai_client,
)
from app.utils.ai_client_parser import (
    fix_common_json_issues,
    infer_test_category,
    infer_action_type,
    extract_input_value_from_expected,
)
from app.utils.ai_client_formatter import (
    normalize_new_format,
    normalize_old_format,
)


def generate_test_case_enhanced(context: Dict[str, Any]) -> Dict[str, Any]:
    graph_prompt = context.get('graph_prompt')
    if graph_prompt:
        prompt = graph_prompt
    else:
        from app.utils.ai_client_prompt import (
            sanitize_input, build_weight_model,
            build_ui_specs_description, build_project_env_info
        )
        requirement = sanitize_input(context.get('requirement', ''))
        test_points = context.get('test_points', [])
        ui_specs = context.get('ui_specs', [])
        project_config = context.get('project_config', {})
        has_requirement = bool(requirement and requirement.strip())
        has_ui = bool(ui_specs)
        has_test_point = bool(test_points)
        weight_desc, weight_example, weight_warning = build_weight_model(has_requirement, has_ui, has_test_point)
        ui_desc = build_ui_specs_description(ui_specs) if has_ui else "无UI原型图解析结果"
        env_desc = build_project_env_info(project_config)
        history_cases = context.get('history_cases', [])
        history_cases_text = ""
        if history_cases:
            history_cases_text = "## 项目已有测试用例（用例评审）\n\n"
            history_cases_text += "以下为项目已有的测试用例，请逐条对照新需求/UI进行评审：\n"
            history_cases_text += "- 查漏：新场景未被任何旧用例覆盖 → 生成新用例（change_type=added）\n"
            history_cases_text += "- 补缺：旧用例的步骤/预期与新代码或UI不一致 → 输出修正后的用例（change_type=modified，parent_case_id=原用例ID）\n"
            history_cases_text += "- 去冗：旧用例对应的场景已不存在 → 标注建议废弃（change_type=deprecated，parent_case_id=原用例ID）\n"
            history_cases_text += "- 保留：旧用例仍完全符合当前场景 → 无需重复生成\n\n"
            for i, case in enumerate(history_cases, 1):
                desc = case.get("summary", "") or case.get("expected_result", "") or "无摘要"
                history_cases_text += f"  {i}. [{case.get('module', '')}] {case.get('title', '')} (ID:{case.get('id', '')}) — {desc}\n"
        test_points_text = ""
        if test_points:
            test_points_text = "## 测试点列表\n"
            for i, tp in enumerate(test_points):
                module = tp.get('module', '')
                function = tp.get('function', '')
                point = tp.get('point', '')
                priority = tp.get('priority', 2)
                test_points_text += f"{i+1}. [{module} - {function}] {point} (优先级:{priority})\n"
        prompt = f"""你是一名高级测试工程师，请根据以下信息生成一个高质量的测试用例。

{weight_desc}

{weight_example}

{weight_warning}

---

## 需求文档
{requirement if has_requirement else "（未提供需求文档）"}

---

## UI原型图解析结果
{ui_desc}

---

{test_points_text}

---

{env_desc}

---

{history_cases_text}

---

## 输出格式要求
请严格按照以下JSON格式输出（不要添加markdown代码块标记）：
{{
  "title": "场景+操作+验证重点（如：无网络时提交批改显示网络错误提示）",
  "module": "所属模块",
  "precondition": "系统已通过配置自动登录至目标页面",
  "case_type": "ui_automation/manual/api_automation/performance/security",
  "test_category": "与case_type保持一致",
  "priority": "P0/P2/P3",
  "test_data": {{"normal": {{}}, "boundary": {{}}, "abnormal": {{}}}},
  "steps": [
    {{
      "step": "1",
      "description": "步骤1描述",
      "action": "具体的业务操作描述",
      "action_type": "click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress",
      "input_value": "输入值（仅input类型有值，其他为空字符串）",
      "target_element": "目标元素描述",
      "expected_result": "该步骤的预期验证条件"
    }}
  ],
  "expected_result": "所有步骤预期结果的汇总描述",
  "change_type": "added/modified/deprecated（无参考用例时为added）",
  "parent_case_id": "原用例ID（仅modified/deprecated时填写，added时为null）"
}}

## 标题规范
- 格式：「场景/条件」+「操作」+「验证重点」，如"未选单词时纸张听写按钮置灰不可点击"
- 看到标题即知用例目的，禁止使用"功能验证""界面测试""XX测试"等模糊词
- 好标题："无网络时提交批改显示网络错误提示""编辑状态下未选中生词删除按钮置灰""输入有效邮箱和密码注册成功"
- 坏标题："功能验证""界面测试""听写功能测试""Video Test Case"
- 长度15-40字

## 前置条件规范
- 必须包含"账号已登录"和"设备网络正常"，有权限相关场景必须补充权限状态（如"相机权限已开启"）
- 禁止仅写"账号已登录"或"APP运行正常"等不完整前置

## 正反用例对比（学习优秀写法，避免差劲写法）

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
✅优秀：首次进入模块，验证引导弹窗展示关闭交互 | 前置：首次进入该模块无弹窗关闭缓存记录 | 步骤：1.进入中文作文批改首页 2.查看页面弹窗内容 3.点击弹窗关闭按钮 | 预期：1.页面加载完成后自动弹出新手引导弹窗 2.弹窗文案图片展示完整样式符合设计 3.弹窗正常关闭首页所有功能按钮可正常点击操作
优点：前置条件严谨区分首次/非首次；覆盖UI+文案+交互+联动多维度；标准统一适合团队协作

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

## 生成规则
1. **步骤要求**：每个步骤必须是原子操作；action_type必须是枚举值之一；input_value仅input/select填写；expected_result必须是可验证条件
2. **用例类型**：ui_automation(UI交互)/manual(人工判断)/api_automation(接口验证)/performance(性能)/security(安全)
3. **优先级**：P0(核心功能)/P2(一般验证)/P3(边界异常)
4. **覆盖要求**：必须覆盖需求文档所有功能点；每个测试点至少一个用例；有UI原型图时操作对象须与UI元素对应
5. **格式统一**：step字段为字符串类型；必须包含test_data字段（normal/boundary/abnormal三个空对象）

前置条件规范：
- 必须包含"账号已登录"和网络环境（Web端写"浏览器网络正常"，App端写"设备网络正常"），有权限相关场景必须补充权限状态（如"相机权限已开启"）
- 禁止仅写"账号已登录"或"APP运行正常"等不完整前置
- 前置条件只约束环境与权限，禁止依赖特定业务数据（如"列表有数据""数据较多"），确保用例任意环境可独立执行；如需特定数据才能测试（如编辑/删除场景），应在步骤中先创建数据，而非在前置中假设数据已存在
- 前置条件不能包含操作步骤或页面导航状态（如"已进入详情页""在列表页面"），导航到达目标页面必须作为步骤体现，确保用例可独立自动化执行

自动化友好规范：
- 步骤和预期必须支持自动化断言，预期结果需有可量化判定标准（如"无白屏""无接口报错""按钮置灰"）
- 禁止"页面正常""功能正常""没问题"等无法断言的模糊描述
- 步骤必须包含从登录后到达目标页面的完整导航操作，禁止将导航隐藏在前置条件中
- 弱网、异常条件等自动化无法实现的场景标注case_type为manual
"""

    client = get_ai_client()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"增强版AI生成测试用例 - 尝试 {attempt + 1}/{max_retries}")
            response = client.chat.completions.create(
                model=client.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # 统一低温度，输出稳定
                max_tokens=2000
            )
            resp_content = response.choices[0].message.content
            if not resp_content:
                raise AIResponseParseError("AI返回内容为空")
            resp_content = resp_content.strip()
            if resp_content.startswith("```"):
                resp_content = re.sub(r'^```(?:json)?\s*\n?', '', resp_content)
                resp_content = re.sub(r'\n?```\s*$', '', resp_content)
                resp_content = resp_content.strip()
            generated_case = None
            try:
                generated_case = json.loads(resp_content)
            except json.JSONDecodeError:
                json_match = re.search(r'\{[\s\S]*\}', resp_content)
                if json_match:
                    try:
                        generated_case = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        fixed = fix_common_json_issues(json_match.group(0))
                        if fixed:
                            try:
                                generated_case = json.loads(fixed)
                            except json.JSONDecodeError:
                                pass
            if generated_case and isinstance(generated_case, dict):
                if 'expected_results' in generated_case and isinstance(generated_case.get('expected_results'), list):
                    generated_case = normalize_new_format(generated_case)
                else:
                    generated_case = normalize_old_format(generated_case)
                logger.info("增强版AI生成测试用例成功")
                return generated_case
            logger.warning(f"AI返回内容无法解析 (尝试 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise AIResponseParseError("AI返回内容无法解析为有效的测试用例")
        except (AIResponseParseError, AIResponseFormatError):
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise
        except Exception as e:
            logger.error(f"增强版AI生成测试用例失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise AIServiceError(f"增强版AI生成测试用例失败: {str(e)}")
    raise AIServiceError("增强版AI生成测试用例失败: 超过最大重试次数")


def generate_test_case(test_point: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if context:
        context['test_points'] = [test_point]
        return generate_test_case_enhanced(context)
    from app.utils.ai_client_core import AIClientBase
    from app.utils.ai_client_test_case import AITestCaseMixin
    class _TempClient(AITestCaseMixin, AIClientBase):
        pass
    client = _TempClient()
    return client.generate_test_case(test_point)


async def analyze_requirements_stream(content: str) -> Any:
    from app.utils.ai_client_core import AIClientBase
    from app.utils.ai_client_stream import AIStreamMixin
    class _TempClient(AIStreamMixin, AIClientBase):
        pass
    client = _TempClient()
    async for chunk in client.analyze_requirements_stream(content):
        yield chunk


async def generate_test_case_stream(test_point: Dict[str, Any]) -> Any:
    from app.utils.ai_client_core import AIClientBase
    from app.utils.ai_client_stream import AIStreamMixin
    class _TempClient(AIStreamMixin, AIClientBase):
        pass
    client = _TempClient()
    async for chunk in client.generate_test_case_stream(test_point):
        yield chunk


def parse_precondition_to_steps(precondition: str) -> List[Dict[str, Any]]:
    if not precondition or not precondition.strip():
        return []
    steps = []
    precondition = precondition.strip()
    patterns = [
        r'(?:步骤\s*)?(\d+)[.、)\]]\s*(.+?)(?=(?:步骤\s*)?\d+[.、)\]]|$)',
        r'(\d+)\.\s*(.+?)(?=\d+\.|$)',
    ]
    matched = False
    for pattern in patterns:
        matches = re.findall(pattern, precondition, re.DOTALL)
        if matches and len(matches) > 1:
            for step_num, step_text in matches:
                step_text = step_text.strip()
                if step_text:
                    action_type = infer_action_type(step_text)
                    steps.append({
                        'step': int(step_num) if step_num.isdigit() else len(steps) + 1,
                        'action': step_text, 'action_type': action_type,
                        'input_value': '', 'target_element': '',
                        'description': f'{len(steps) + 1}. {step_text}',
                        'expected_result': f'{step_text}完成',
                        'test_data': [], 'ui_elements': []
                    })
            matched = True
            break
    if not matched:
        line_pattern = r'[;；\n]+'
        lines = re.split(line_pattern, precondition)
        lines = [line.strip() for line in lines if line.strip()]
        if len(lines) > 1:
            for i, line in enumerate(lines):
                action_type = infer_action_type(line)
                steps.append({
                    'step': i + 1, 'action': line, 'action_type': action_type,
                    'input_value': '', 'target_element': '',
                    'description': f'{i + 1}. {line}',
                    'expected_result': f'{line}完成',
                    'test_data': [], 'ui_elements': []
                })
        else:
            action_type = infer_action_type(precondition)
            steps.append({
                'step': 1, 'action': precondition, 'action_type': action_type,
                'input_value': '', 'target_element': '',
                'description': f'1. {precondition}',
                'expected_result': f'{precondition}完成',
                'test_data': [], 'ui_elements': []
            })
    return steps
