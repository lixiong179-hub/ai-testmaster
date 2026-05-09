import requests
import json
import re
import time
from typing import Dict, Any, Optional, List
from loguru import logger

from app.utils.ai_client_core import (
    AIClientBase,
    AIServiceError,
    AIResponseParseError,
    AIResponseFormatError,
    _detect_ai_error,
)
from app.utils.ai_client_formatter import (
    normalize_new_format,
    normalize_old_format,
)


class AITestCaseMixin:
    def analyze_requirements(self, content: str) -> List[Dict[str, Any]]:
        cache_key = self._get_cache_key("analyze_requirements", content)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        prompt_template = (
            "你是一名专业的测试工程师，请根据以下需求内容分析并提取结构化测试点：\n\n"
            "需求内容：\n{REQ_CONTENT_PLACEHOLDER}\n\n"
            "请按照以下格式提取测试点：\n"
            "1. 按模块分组，每个模块下的测试点要逻辑清晰\n"
            "2. 每个测试点必须包含：\n"
            "   - module: 模块名称\n"
            "   - function: 功能名称\n"
            "   - point: 测试点描述（必须具体明确，突出测试重点）\n"
            "   - priority: 优先级（1高/2中/3低）\n"
            "3. 测试点要求：具体明确、覆盖全面、逻辑独立、可执行\n\n"
            "测试点描述规范：\n"
            "- 必须包含：场景/条件 + 具体操作 + 验证重点，让人一看就知道要测什么\n"
            "- 要突出边界值、并发、异常、竞态等容易出bug的场景，不要只写正常流程\n"
            "- 好的测试点示例：\n"
            "  · 登录失败次数达到上限后，立即输入正确密码，观察锁定倒计时是否真正生效\n"
            "  · 订单金额刚好满足满200减30门槛时，取消其中一件商品使金额低于200，检查优惠是否即时撤销\n"
            "  · 10个用户在同一秒内抢购最后1件库存商品，最终是否只有1人下单成功且库存变为0\n"
            "  · 页面加载过程中，狂点同一个提交按钮10次，最终是否只产生一次有效请求\n"
            "  · 在弱网环境下，大文件上传中断后自动重传，文件完整性是否无损\n"
            "- 坏的测试点示例：\n"
            "  · 测试登录功能 — 太模糊，没有指向任何具体风险点\n"
            "  · 验证页面在极端网络下正常展示 — 缺少具体条件，\"极端\"和\"正常\"不可衡量\n"
            "  · 检查数据库是否收到正确数据 — 脱离用户视角，只关注实现细节\n"
            "  · 用100个窗口同时点击结算 — 场景失真，且没有明确的通过标准\n\n"
            "请严格以JSON格式输出：\n[\n  {\n"
            '    "module": "用户管理",\n'
            '    "function": "登录",\n'
            '    "point": "登录失败次数达到上限后，立即输入正确密码，观察锁定倒计时是否真正生效",\n'
            '    "priority": 1\n  }\n]\n\n'
            "重要要求：只输出JSON，确保格式正确，测试点必须具体明确突出测试重点，优先级合理，覆盖所有重要功能点（含边界和异常场景）\n"
        )
        prompt = prompt_template.replace("{REQ_CONTENT_PLACEHOLDER}", content)
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,  # 统一低温度，输出稳定
            "max_tokens": 2000
        }
        for attempt in range(self.max_retries):
            try:
                logger.info(f"AI分析需求 - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(self.api_url, headers=headers, json=data, timeout=60)
                response.raise_for_status()
                result = response.json()
                resp_content = result["choices"][0]["message"]["content"]
                test_points = None
                try:
                    parsed = json.loads(resp_content)
                    if isinstance(parsed, list):
                        test_points = parsed
                except json.JSONDecodeError:
                    json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', resp_content)
                    if json_match:
                        try:
                            test_points = json.loads(json_match.group(0))
                        except json.JSONDecodeError:
                            pass
                if test_points is not None:
                    logger.info("AI分析需求成功")
                    self._set_to_cache(cache_key, test_points)
                    return test_points
                logger.warning("AI返回的内容不是有效的JSON格式")
                return []
            except requests.RequestException as e:
                logger.error(f"AI分析需求失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    error = _detect_ai_error(e)
                    logger.error(error.message)
                    raise error
            except AIServiceError:
                raise
            except Exception as e:
                logger.error(f"AI分析需求失败: {str(e)}")
                raise AIServiceError(f"AI分析需求失败: {str(e)}")

    def generate_test_case(self, test_point: Dict[str, Any]) -> Dict[str, Any]:
        cache_key = self._get_cache_key("generate_test_case", test_point)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        module = test_point.get('module', '未知模块')
        function = test_point.get('function', '')
        point = test_point.get('point', '')
        priority = test_point.get('priority', 2)
        prompt = f"""你是一名专业的测试工程师，请根据以下测试点生成可执行的测试用例：

模块：{module}
功能：{function}
测试点：{point}
优先级：{priority}（1高/2中/3低）

请按照以下格式生成测试用例：
1. 用例标题（必须具体明确，格式：场景/条件+操作+验证重点）
2. 前置条件
3. 可执行步骤
4. 预期结果
5. 用例类型（ui_automation/manual/api_automation/performance/security）

标题规范：
- 格式：「场景/条件」+「操作」+「验证重点」，如"未选单词时纸张听写按钮置灰不可点击"
- 看到标题即知用例目的，禁止使用"功能验证""界面测试""XX测试"等模糊词
- 好标题："无网络时提交批改显示网络错误提示""编辑状态下未选中生词删除按钮置灰""输入有效邮箱和密码注册成功"
- 坏标题："功能验证""界面测试""听写功能测试""Video Test Case"
- 长度15-40字

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

请以JSON格式输出，结构如下：
{{
  "title": "场景+操作+验证重点",
  "precondition": "前置条件",
  "steps": [
    {{
      "step": 1,
      "action": "业务操作描述",
      "action_type": "click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress",
      "input_value": "输入值（仅input类型有值，其他为空字符串）",
      "target_element": "目标元素描述",
      "expected_result": "该步骤的预期验证条件"
    }}
  ],
  "expected_results": ["步骤1的预期验证条件", "步骤2的预期验证条件"],
  "case_type": "ui_automation/manual/api_automation/performance/security",
  "test_category": "与case_type保持一致"
}}

重要要求：
1. 只输出JSON格式内容，不要添加任何其他文字
2. 确保JSON格式正确，可直接被解析
3. 步骤要详细、可执行，参数要明确
4. action_type必须是以下枚举之一：click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress
5. expected_results中每条必须是验证条件，不包含输入值
"""
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,  # 统一低温度，输出稳定
            "max_tokens": 1500
        }
        for attempt in range(self.max_retries):
            try:
                logger.info(f"AI生成测试用例 - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                resp_content = result["choices"][0]["message"]["content"]
                generated_case = self._parse_generate_response(resp_content)
                if generated_case:
                    logger.info("AI生成测试用例成功")
                    self._set_to_cache(cache_key, generated_case)
                    return generated_case
                raise AIResponseParseError()
            except requests.RequestException as e:
                logger.error(f"AI生成测试用例失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    error = _detect_ai_error(e)
                    logger.error(error.message)
                    raise error
            except AIServiceError:
                raise
            except json.JSONDecodeError as e:
                logger.error(f"AI返回内容解析失败: {str(e)}")
                raise AIResponseParseError()
            except Exception as e:
                logger.error(f"AI生成测试用例失败: {str(e)}")
                raise AIServiceError(f"AI生成测试用例失败: {str(e)}")

    def _parse_generate_response(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            generated_case = json.loads(content)
            if isinstance(generated_case, dict):
                return self._validate_and_normalize_case(generated_case)
        except json.JSONDecodeError:
            pass
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                generated_case = json.loads(json_match.group(0))
                return self._validate_and_normalize_case(generated_case)
            except (json.JSONDecodeError, Exception):
                logger.warning("提取的JSON格式错误")
                raise AIResponseParseError()
        logger.warning("AI返回的内容不是有效的JSON格式")
        raise AIResponseParseError()

    def _validate_and_normalize_case(self, generated_case: Dict[str, Any]) -> Dict[str, Any]:
        required_fields = ['title', 'precondition', 'steps']
        missing_fields = [f for f in required_fields if f not in generated_case]
        if missing_fields:
            logger.warning(f"AI返回的JSON缺少必要字段: {missing_fields}")
            raise AIResponseFormatError(f"AI响应缺少必要字段: {', '.join(missing_fields)}")
        if 'expected_results' in generated_case and isinstance(generated_case.get('expected_results'), list):
            generated_case = normalize_new_format(generated_case)
            logger.info("检测到新格式(expected_results分离)，已标准化")
        elif 'steps' in generated_case:
            generated_case = normalize_old_format(generated_case)
            logger.info("检测到旧格式，已标准化为P0/P2/P3优先级")
        return generated_case
