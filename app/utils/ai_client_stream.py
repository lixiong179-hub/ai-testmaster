"""
AI流式响应处理模块

本模块实现AI服务的SSE（Server-Sent Events）流式响应处理，是AI客户端分层架构中的"流式层"。
流式响应的核心价值是实时向客户端推送处理进度，避免长时间等待无反馈。

核心类：
    - AIStreamMixin: 流式处理Mixin，提供两个异步生成器方法

核心方法：
    - analyze_requirements_stream: 流式分析需求，实时推送分析进度
    - generate_test_case_stream: 流式生成测试用例，实时推送生成进度

流式响应处理流程：
    1. 构建请求Payload（stream=True）
    2. 通过requests.post发送流式请求
    3. 逐chunk解析SSE数据（data: {...}格式）
    4. 累积完整内容并计算进度百分比
    5. 流式接收完成后，解析完整内容为结构化数据
    6. 解析失败时降级到fallback提取策略

错误处理策略：
    - 网络错误：自动重试（max_retries次），每次间隔retry_delay秒
    - AI服务错误：通过_detect_ai_error映射为业务异常
    - 解析错误：降级到fix_common_json_issues和extract_json_objects_fallback

依赖：
    - requests: HTTP请求库（同步流式）
    - app.utils.ai_client_core: 异常体系和错误检测
    - app.utils.ai_client_parser: JSON修复和兜底提取
"""
import requests
import json
import re
import time
from typing import Dict, Any, Optional, AsyncGenerator, List
from loguru import logger

from app.utils.ai_client_core import (
    AIServiceError,
    AIResponseParseError,
    _detect_ai_error,
)
from app.utils.ai_client_parser import (
    fix_common_json_issues,
    extract_json_objects_fallback,
)


class AIStreamMixin:
    """AI流式响应处理Mixin

    为AIClient提供SSE流式响应处理能力。通过Mixin模式组合到AIClient中，
    避免流式处理逻辑与核心业务逻辑耦合。

    该Mixin依赖AIClientBase提供的以下属性：
    - self.api_url: AI API端点地址
    - self.api_key: API密钥
    - self.model: 模型名称
    - self.max_retries: 最大重试次数
    - self.retry_delay: 重试间隔秒数
    """

    async def analyze_requirements_stream(self, content: str) -> AsyncGenerator[Dict[str, Any], None]:
        """流式分析需求文档，提取结构化测试点

        向AI发送需求分析请求，通过SSE流式接收响应，实时推送进度。
        每次yield一个字典，包含progress（0-100）、message和可选的data字段。

        Args:
            content: 需求文档内容文本

        Yields:
            Dict[str, Any]: 进度消息字典
                - progress: 进度百分比（0-100）
                - message: 进度描述文本
                - data: 最终结果数据（仅progress=100时存在）
                - error: 错误标记（仅出错时存在）
                - status: 状态标记（"error"表示出错）
        """
        logger.info(f"开始AI分析需求（流式），输入内容长度: {len(content)} 字符")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        prompt_template = (
            "你是一名资深测试工程师，请根据以下需求内容分析并提取结构化测试点：\n\n"
            "需求内容：\n{REQ_CONTENT_PLACEHOLDER}\n\n"
            "## 测试点提取规则\n"
            "1. 按模块分组，每个模块下的测试点要逻辑清晰、不重复\n"
            "2. 每个测试点必须包含：module（模块名称）、function（功能名称）、point（测试点描述）、priority（1高/2中/3低）\n"
            "3. **禁止重复**：同一模块下不允许出现测试价值重复的测试点（如多条「进入XX模块」），入口校验只需一条\n"
            "4. **必须有验证目标**：测试点必须说明要验证什么结果，不能只描述操作动作\n"
            "5. **覆盖异常和边界**：必须覆盖无网络、无数据、权限异常、重复提交、边界值等场景，不能只有正常流程\n"
            "6. **优先级合理**：核心流程、数据保存、关键交互设为1（高）；一般验证设为2（中）；边缘场景设为3（低）\n\n"
            "## 测试点描述规范\n"
            "- 格式：「场景/条件」+「操作」+「验证重点」，让人一看就知道要测什么、怎么判断通过\n"
            "- 必须包含可观察的预期结果，如「页面应展示XX」「系统应提示XX」「数据应保存为XX」\n"
            "- 禁止写纯操作步骤（如「进入模块」「点击按钮」），必须附带验证目标\n"
            "- 禁止模糊描述（如「测试XX功能」「验证是否正常」），「正常」不可衡量\n"
            "- 粒度适中：一个测试点对应一个可独立执行的验证场景，不要把整个功能塞进一条\n"
            "- 要突出边界值、并发、异常、竞态等容易出bug的场景，不要只写正常流程\n\n"
            "## 正反示例\n"
            "❌差劲测试点：\n"
            "1. 进入字词听写模块 — 太泛，只描述操作没有验证目标\n"
            "2. 点击按钮 — 信息缺失，未说明点击哪个按钮、预期什么结果\n"
            "3. 测试字词听写是否正常 — 不可执行，「正常」没有明确定义\n"
            "4. 账号已登录，进入模块 — 不是测试点，是前置条件+操作步骤的组合\n"
            "5. 听写功能测试 — 粒度过大，包含了加载、播放、提交等多个环节\n\n"
            "✅优秀测试点：\n"
            "1. 已登录用户进入字词听写模块后，页面应正确展示当前教材、单元列表和可听写字词数量 | 优先级：高\n"
            "   优点：明确验证入口加载结果，不只是「进入模块」，覆盖UI与数据渲染校验\n"
            "2. 用户选择一个有字词数据的单元后，系统应展示该单元下的字词列表，并支持开始听写 | 优先级：高\n"
            "   优点：覆盖核心路径：选单元→展示字词→开始听写，流程完整且目标明确\n"
            "3. 用户开始听写后，系统应按顺序播放字词音频，并在播放失败时给出重试提示 | 优先级：高\n"
            "   优点：同时覆盖核心功能和异常处理，能有效发现音频播放、容错逻辑缺陷\n"
            "4. 用户完成听写并提交后，系统应正确展示正确数、错误数、得分，并保存听写记录 | 优先级：高\n"
            "   优点：有明确结果校验，覆盖业务闭环，验证了数据落库与前端展示一致性\n"
            "5. 用户听写错误的字词应自动进入错词记录，并可在错词本中查看 | 优先级：中\n"
            "   优点：覆盖数据流转，验证模块间关联逻辑\n\n"
            "请严格以JSON格式输出：\n[\n  {\n"
            '    "module": "模块名称",\n'
            '    "function": "功能名称",\n'
            '    "point": "测试点描述（场景/条件+操作+验证重点）",\n'
            '    "priority": 1\n  }\n]\n\n'
            "重要要求：只输出JSON，确保格式正确，测试点必须具体明确有验证目标，禁止重复，优先级合理，必须覆盖异常和边界场景，至少输出5个测试点\n"
        )
        prompt = prompt_template.replace("{REQ_CONTENT_PLACEHOLDER}", content)
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 4096,
            "stream": True
        }
        full_content = ""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"AI分析需求（流式响应） - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(self.api_url, headers=headers, json=data, stream=True, timeout=120)
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        chunk_str = chunk.decode('utf-8')
                        lines = chunk_str.split('\n')
                        for line in lines:
                            if line.startswith('data: '):
                                data_part = line[6:]
                                if data_part == '[DONE]':
                                    break
                                try:
                                    chunk_data = json.loads(data_part)
                                    if 'choices' in chunk_data:
                                        delta = chunk_data['choices'][0].get('delta', {})
                                        if 'content' in delta:
                                            full_content += delta['content']
                                            progress = min(int(len(full_content) / 20), 95)
                                            yield {"progress": progress, "message": "分析中..."}
                                except json.JSONDecodeError:
                                    pass
                logger.info(f"AI流式响应接收完成，内容长度: {len(full_content)} 字符")
                test_points = self._parse_stream_test_points(full_content)
                if test_points is not None:
                    yield {"progress": 100, "message": "分析完成", "data": test_points}
                    return
                raise AIResponseParseError()
            except requests.RequestException as e:
                logger.error(f"AI分析需求失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    error = _detect_ai_error(e)
                    logger.error(error.message)
                    yield {"progress": 100, "message": error.message, "status": "error", "error": True}
                    return
            except AIServiceError as e:
                yield {"progress": 100, "message": e.message, "status": "error", "error": True}
                return
            except Exception as e:
                error_message = f"分析失败: {str(e)}"
                logger.error(error_message)
                yield {"progress": 100, "message": error_message, "status": "error", "error": True}
                return

    def _parse_stream_test_points(self, full_content: str) -> Optional[List[Dict[str, Any]]]:
        """解析流式响应的完整内容为测试点列表

        采用多级降级解析策略：
        1. 直接JSON解析
        2. 从Markdown代码块（```json...```）中提取后解析
        3. 正则匹配JSON数组后解析
        4. 上述均失败时，使用fix_common_json_issues修复后重试
        5. 最终降级到extract_json_objects_fallback兜底提取

        Args:
            full_content: 流式响应累积的完整文本内容

        Returns:
            Optional[List[Dict[str, Any]]]: 解析成功的测试点列表，全部失败返回None
        """
        try:
            test_points = json.loads(full_content)
            if isinstance(test_points, list):
                logger.info("AI分析需求（流式响应）成功")
                return test_points
        except json.JSONDecodeError:
            pass
        json_match = re.search(r'```(?:json)?\s*\n?(\[[\s\S]*?\])\s*\n?```', full_content)
        if json_match:
            json_str = json_match.group(1)
            try:
                test_points = json.loads(json_str)
                logger.info("AI分析需求（流式响应）成功 - 从markdown代码块提取")
                return test_points
            except json.JSONDecodeError:
                fixed_json = fix_common_json_issues(json_str)
                if fixed_json:
                    try:
                        test_points = json.loads(fixed_json)
                        logger.info("AI分析需求（流式响应）成功 - JSON已修复")
                        return test_points
                    except json.JSONDecodeError:
                        pass
        json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', full_content)
        if json_match:
            json_str = json_match.group(0)
            try:
                test_points = json.loads(json_str)
                logger.info("AI分析需求（流式响应）成功")
                return test_points
            except json.JSONDecodeError:
                fixed_json = fix_common_json_issues(json_str)
                if fixed_json:
                    try:
                        test_points = json.loads(fixed_json)
                        logger.info("AI分析需求（流式响应）成功 - JSON已修复")
                        return test_points
                    except json.JSONDecodeError:
                        pass
        logger.warning(f"AI返回的内容无法解析为JSON。内容长度: {len(full_content)}")
        logger.warning(f"内容前500字符: {full_content[:500]}")
        debug_file = "ai_response_debug.txt"
        try:
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(full_content)
            logger.info(f"完整AI响应已保存到: {debug_file}")
        except Exception as e:
            logger.warning(f"无法保存调试文件: {e}")
        test_points = extract_json_objects_fallback(full_content)
        if test_points:
            logger.info(f"使用fallback方法成功提取 {len(test_points)} 个测试点")
            return test_points
        return None

    async def generate_test_case_stream(self, test_point: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """流式生成单个测试用例

        根据给定的测试点，通过SSE流式请求AI生成完整的测试用例。
        生成完成后验证必要字段（title、precondition、steps、expected_result、case_type），
        缺少任何字段都会返回错误。

        Args:
            test_point: 测试点字典，包含module、function、point、priority字段

        Yields:
            Dict[str, Any]: 进度消息字典
                - progress: 进度百分比（0-100）
                - message: 进度描述文本
                - data: 生成的测试用例数据（仅成功时存在）
                - error: 错误标记（仅出错时存在）
                - status: 状态标记（"error"表示出错）
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        prompt = f"""你是一名专业的测试工程师，请根据以下测试点生成可执行的测试用例：

模块：{test_point.get('module', '未知模块')}
功能：{test_point.get('function', '')}
测试点：{test_point.get('point', '')}
优先级：{test_point.get('priority', 2)}（1高/2中/3低）

请按照以下格式生成测试用例：
1. 用例标题（必须具体明确，格式：场景/条件+操作+验证重点）
2. 前置条件
3. 可执行步骤
4. 预期结果
5. 用例类型

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
      "input_value": "输入值",
      "target_element": "目标元素描述",
      "expected_result": "该步骤的预期验证条件"
    }}
  ],
  "expected_results": ["步骤1的预期验证条件"],
  "case_type": "UI/API/功能",
  "test_category": "ui_automation/manual/api_automation"
}}

重要要求：只输出JSON，格式正确，步骤详细可执行，action_type使用枚举值
"""
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,  # 统一低温度，输出稳定
            "max_tokens": 1500,
            "stream": True
        }
        full_content = ""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"AI生成测试用例（流式响应） - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(self.api_url, headers=headers, json=data, stream=True, timeout=60)
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        chunk_str = chunk.decode('utf-8')
                        lines = chunk_str.split('\n')
                        for line in lines:
                            if line.startswith('data: '):
                                data_part = line[6:]
                                if data_part == '[DONE]':
                                    break
                                try:
                                    chunk_data = json.loads(data_part)
                                    if 'choices' in chunk_data:
                                        delta = chunk_data['choices'][0].get('delta', {})
                                        if 'content' in delta:
                                            full_content += delta['content']
                                            progress = min(int(len(full_content) / 15), 95)
                                            yield {"progress": progress, "message": "生成中..."}
                                except json.JSONDecodeError:
                                    pass
                try:
                    generated_case = json.loads(full_content)
                    if isinstance(generated_case, dict):
                        required_fields = ['title', 'precondition', 'steps', 'expected_result', 'case_type']
                        missing_fields = [f for f in required_fields if f not in generated_case]
                        if missing_fields:
                            yield {"progress": 100, "message": f"AI响应缺少必要字段: {', '.join(missing_fields)}", "status": "error", "error": True}
                            return
                        yield {"progress": 100, "message": "生成完成", "data": generated_case}
                        return
                except json.JSONDecodeError:
                    json_match = re.search(r'\{\s*"title"[\s\S]*\}', full_content)
                    if json_match:
                        try:
                            generated_case = json.loads(json_match.group(0))
                            required_fields = ['title', 'precondition', 'steps', 'expected_result', 'case_type']
                            missing_fields = [f for f in required_fields if f not in generated_case]
                            if missing_fields:
                                yield {"progress": 100, "message": f"AI响应缺少必要字段: {', '.join(missing_fields)}", "status": "error", "error": True}
                                return
                            yield {"progress": 100, "message": "生成完成", "data": generated_case}
                            return
                        except json.JSONDecodeError:
                            pass
                yield {"progress": 100, "message": "AI响应格式错误，无法解析", "status": "error", "error": True}
                return
            except requests.RequestException as e:
                logger.error(f"AI生成测试用例失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    error = _detect_ai_error(e)
                    yield {"progress": 100, "message": error.message, "status": "error", "error": True}
                    return
            except AIServiceError as e:
                yield {"progress": 100, "message": e.message, "status": "error", "error": True}
                return
            except Exception as e:
                error_message = f"生成失败: {str(e)}"
                logger.error(error_message)
                yield {"progress": 100, "message": error_message, "status": "error", "error": True}
                return
