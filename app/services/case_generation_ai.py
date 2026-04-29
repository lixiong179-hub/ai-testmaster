"""用例生成AI Mixin - DeepSeek API调用、Prompt构建与响应解析。

本模块封装与DeepSeek AI API的交互逻辑，包括Prompt构建、
API调用（含重试机制）和AI响应解析。作为AIMixin被
TestCaseGenerationService组合使用。

核心类:
    - AIMixin: AI调用Mixin，提供用例生成的AI能力

设计模式:
    作为Mixin模块，通过多继承组合到TestCaseGenerationService中，提供:
    - _generate_case_with_ai: AI生成核心方法（含重试）
    - _build_generation_prompt: Prompt构建
    - _format_ui_spec_for_prompt: UI规格格式化
    - _parse_ai_response: AI响应解析

依赖关系:
    - app.utils.ai_client: AI客户端工具
    - app.core.config: 配置管理（API密钥、模型名称等）

AI调用流程:
    1. 构建生成Prompt（需求+UI+测试点信息）
    2. 调用DeepSeek API（最多3次重试，指数退避）
    3. 解析AI返回的JSON格式用例数据

安全设计:
    - API密钥通过settings配置读取，禁止硬编码
    - Prompt注入防护由ContentSanitizer在调用前处理
    - AI响应解析采用宽松匹配策略，兼容格式偏差
"""
import json
import re
from typing import List, Dict, Any, Optional
from loguru import logger

from app.utils.ai_client import AIServiceError
from app.core.config import settings


class AIMixin:
    """AI调用Mixin - 封装DeepSeek API交互与响应解析。

    职责:
        - 构建结构化的AI生成Prompt
        - 调用DeepSeek API并处理重试逻辑
        - 解析AI返回的JSON格式用例数据
        - 格式化UI规格数据为Prompt友好的文本

    设计意图:
        将AI调用逻辑从生成流程中抽离，便于:
        1. 独立测试AI调用和响应解析
        2. 替换不同的AI服务提供商
        3. 统一管理重试策略和错误处理

    使用场景:
        被TestCaseGenerationService通过多继承组合，
        在生成流程中调用_generate_case_with_ai获取AI生成的用例数据。

    重试策略:
        - 最大重试次数: 3次
        - 退避策略: 指数退避（2^attempt秒）
        - 超时时间: 60秒
        - 可重试异常: TimeoutException, HTTPStatusError, RequestError
        - 不可重试异常: ValueError, JSONDecodeError（响应格式错误）
    """

    async def _generate_case_with_ai(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """调用DeepSeek AI生成测试用例，含重试机制。

        调用流程:
            1. 从上下文中提取需求内容、UI描述和测试点
            2. 构建结构化Prompt
            3. 调用DeepSeek API（httpx异步客户端）
            4. 解析AI响应为JSON格式用例数据
            5. 失败时按指数退避重试

        Args:
            context: 生成上下文字典，需包含:
                - requirement_content: 需求文档内容
                - ui_description: UI描述文本
                - ui_specs: UI规格列表
                - test_point: 测试点信息（module/function/point/priority）

        Returns:
            AI生成的用例数据字典，包含:
                - title: 用例标题
                - module: 模块名称
                - precondition: 前置条件
                - steps: 测试步骤列表
                - expected_result: 预期结果
                - case_type: 用例类型
                - case_category: 用例分类
                - priority: 优先级

        Raises:
            ValueError: AI生成失败（重试耗尽或响应格式错误）。
        """
        import httpx

        # 从上下文中提取生成所需信息
        requirement_content = context.get("requirement_content", "")
        ui_description = context.get("ui_description", "")
        ui_specs = context.get("ui_specs", [])
        test_point = context.get("test_point", {})
        module = test_point.get("module", "未知模块")
        function = test_point.get("function", "未知功能")
        point = test_point.get("point", "")
        priority = test_point.get("priority", 2)

        # 构建结构化Prompt
        prompt = self._build_generation_prompt(
            requirement_content=requirement_content, ui_description=ui_description,
            module=module, function=function, point=point, priority=priority, ui_specs=ui_specs
        )

        # 构建API请求头和载荷
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"
        }
        payload = {
            "model": settings.DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,  # 适中的创造性，保证用例多样性
            "max_tokens": 3000   # 限制输出长度，控制成本
        }

        # 重试机制：最多3次，指数退避
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                    response = await client.post(
                        settings.DEEPSEEK_API_URL, headers=headers, json=payload
                    )
                    response.raise_for_status()
                    result = response.json()

                    # 校验AI响应格式
                    if "choices" not in result:
                        raise ValueError("AI API响应格式错误：缺少choices字段")
                    choices = result["choices"]
                    if not choices or len(choices) == 0:
                        raise ValueError("AI API返回结果为空")
                    first_choice = choices[0]
                    if "message" not in first_choice:
                        raise ValueError("AI响应格式错误：缺少message字段")

                    message = first_choice["message"]
                    content = message.get("content", "")
                    if not content:
                        raise ValueError("AI响应内容为空")

                    # 解析AI响应为结构化用例数据
                    generated_case = self._parse_ai_response(content)
                    return generated_case

            except httpx.TimeoutException as e:
                # 超时异常，可重试
                last_error = f"AI API请求超时 (尝试 {attempt + 1}/{max_retries})"
                logger.warning(last_error)
                if attempt < max_retries - 1:
                    await self._async_sleep(2 ** attempt)  # 指数退避: 1s, 2s, 4s
            except httpx.HTTPStatusError as e:
                # HTTP状态码错误，可重试（可能是临时服务不可用）
                last_error = f"AI API HTTP错误: {e.response.status_code}"
                logger.error(last_error)
                if attempt < max_retries - 1:
                    await self._async_sleep(2 ** attempt)
            except httpx.RequestError as e:
                # 网络请求错误，可重试
                last_error = f"AI API请求错误: {str(e)}"
                logger.error(last_error)
                if attempt < max_retries - 1:
                    await self._async_sleep(2 ** attempt)
            except (ValueError, json.JSONDecodeError) as e:
                # 响应格式错误，不重试（重试结果大概率相同）
                last_error = f"AI响应解析失败: {str(e)}"
                logger.error(last_error)
                raise

        # 重试耗尽，抛出异常
        logger.error(f"AI生成失败，已重试{max_retries}次: {last_error}")
        raise ValueError(f"AI生成失败: {last_error}")

    def _build_generation_prompt(
        self, requirement_content: str, ui_description: str,
        module: str, function: str, point: str, priority: int,
        ui_specs: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """构建AI用例生成的结构化Prompt。

        Prompt结构:
            1. 角色设定（资深测试工程师）
            2. 测试点信息（JSON格式，便于AI解析）
            3. 需求文档内容
            4. UI原型信息（规格优先，描述次之）
            5. 输出格式要求（JSON结构定义）
            6. 用例分类标签说明

        UI信息优先级:
            1. UI规格（解析后的结构化数据）-> 最详细
            2. UI描述（文本摘要）-> 次之
            3. 无UI信息 -> 标注"无UI原型图信息"

        Args:
            requirement_content: 需求文档内容。
            ui_description: UI描述文本。
            module: 模块名称。
            function: 功能名称。
            point: 测试点描述。
            priority: 优先级(1高/2中/3低)。
            ui_specs: UI规格列表，可选。

        Returns:
            完整的Prompt字符串。
        """
        # 格式化UI规格数据为Prompt文本
        ui_spec_text = ""
        if ui_specs:
            spec_parts = []
            for spec_item in ui_specs:
                screen_name = spec_item.get("screen_name", "未命名页面")
                spec = spec_item.get("ui_spec", {})
                if spec:
                    spec_parts.append(self._format_ui_spec_for_prompt(screen_name, spec))
            if spec_parts:
                ui_spec_text = "\n\n".join(spec_parts)

        # UI信息优先级：规格 > 描述 > 无
        ui_section = ""
        if ui_spec_text:
            ui_section = f"## UI原型图解析结果（验收标准，优先参考）：\n{ui_spec_text}"
        elif ui_description and ui_description.strip():
            ui_section = f"## UI原型图描述：\n{ui_description}"
        else:
            ui_section = "## UI原型图描述：[无UI原型图信息]"

        # 测试点信息序列化为JSON，便于AI准确解析
        test_point_json = json.dumps({
            "module": module, "function": function, "point": point, "priority": priority
        }, ensure_ascii=False)

        return f"""你是一名资深测试工程师，拥有10年以上的测试经验。请根据以下信息生成详细的、可执行的测试用例。

## 测试点信息（JSON格式）：
{test_point_json}

## 需求文档内容：
{requirement_content if requirement_content else '[无需求文档内容]'}

{ui_section}

## 输出要求：
1. 只输出JSON格式内容，不要添加任何其他文字
2. JSON必须包含以下字段：
   - title: 用例标题
   - module: 模块名称
   - precondition: 前置条件
   - test_data: 测试数据对象
   - steps: 测试步骤数组，每个步骤必须包含：
     * step: 步骤序号（如"1"、"2"、"3"等）
     * description: 步骤描述
     * action: 具体操作
     * expected_result: 该步骤对应的预期结果
   - expected_result: 总体预期结果
   - case_type: 用例类型（ui_automation/manual/api_automation/performance/security）
   - priority: 优先级（1高/2中/3低）
   - case_category: 用例分类标签（ui_automation=UI自动化测试, manual=手工测试, api_automation=接口自动化测试）

## 用例分类标签说明：
- ui_automation: UI自动化测试用例 - 可通过Selenium/Appium等工具自动化执行
- manual: 手工测试用例 - 需要人工执行，无法自动化
- api_automation: 接口自动化测试用例 - 通过HTTP请求验证后端逻辑

根据测试点的性质和界面复杂度判断：
- 涉及UI交互（表单、按钮、输入）→ ui_automation（如果元素可定位）或 manual（如果元素难以定位）
- 纯后端逻辑验证（API调用、数据校验）→ api_automation
- 复杂用户体验测试 → manual

## 输出JSON格式：
{{
  "title": "用例标题",
  "module": "模块名称",
  "precondition": "前置条件",
  "test_data": {{"normal": {{}}, "boundary": {{}}, "abnormal": {{}}}},
  "steps": [
    {{"step": "1", "description": "步骤1描述", "action": "具体操作", "expected_result": "步骤1的预期结果"}},
    {{"step": "2", "description": "步骤2描述", "action": "具体操作", "expected_result": "步骤2的预期结果"}}
  ],
  "expected_result": "总体预期结果",
  "case_type": "ui_automation",
  "case_category": "ui_automation",
  "priority": 优先级
}}"""

    def _format_ui_spec_for_prompt(self, screen_name: str, ui_spec: Dict[str, Any]) -> str:
        """将UI规格数据格式化为Prompt友好的文本描述。

        格式化内容包括:
            - 页面功能描述
            - 页面区域划分
            - 页面元素列表（类型、标签、状态、交互性）
            - 导航结构
            - 布局约束
            - 页面跳转关系

        Args:
            screen_name: 页面名称。
            ui_spec: UI规格字典，包含purpose/regions/elements/navigation等。

        Returns:
            格式化后的文本描述。
        """
        parts = [f"【页面：{screen_name}】"]

        # 页面功能描述
        if ui_spec.get('purpose'):
            parts.append(f"页面功能：{ui_spec['purpose']}")

        # 页面区域划分
        regions = ui_spec.get('regions', {})
        if regions:
            parts.append("页面区域：")
            if isinstance(regions, dict):
                for region_name, region_desc in regions.items():
                    if region_desc:
                        parts.append(f"  - {region_name}: {region_desc}")
            elif isinstance(regions, list):
                for region in regions:
                    if isinstance(region, dict):
                        name = region.get('name', '')
                        desc = region.get('desc', region.get('description', ''))
                        if name or desc:
                            parts.append(f"  - {name}: {desc}")

        # 页面元素列表，限制最多30个避免Prompt过长
        elements = ui_spec.get('elements', [])
        if elements:
            parts.append(f"页面元素（共{len(elements)}个）：")
            for elem in elements[:30]:
                elem_type = elem.get('type', '未知')
                label = elem.get('label', '') or elem.get('semantic', '') or elem.get('name', '')
                state = elem.get('state', 'normal')
                interactive = elem.get('interactive', False)
                desc = elem.get('description', '')
                parts.append(f"  - [{elem_type}] {label} | 状态:{state} | 可交互:{interactive} | {desc}")

        # 导航结构
        navigation = ui_spec.get('navigation', {})
        if navigation:
            parts.append("导航结构：")
            for nav_key, nav_val in navigation.items():
                if nav_val:
                    parts.append(f"  - {nav_key}: {nav_val}")

        # 布局约束，限制最多10项
        layout_checks = ui_spec.get('layout_constraints', [])
        if layout_checks:
            parts.append(f"布局约束（共{len(layout_checks)}项）：")
            for check in layout_checks[:10]:
                desc = check.get('description', '')
                if desc:
                    parts.append(f"  - {desc}")

        # 页面跳转关系
        flows = ui_spec.get('flows', {})
        if flows:
            next_screens = flows.get('expected_next_screens', [])
            if next_screens:
                parts.append(f"预期跳转页面：{', '.join(next_screens)}")

        return "\n".join(parts)

    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """解析AI响应内容为JSON格式用例数据。

        解析策略:
            1. 直接JSON解析（理想情况）
            2. 正则提取JSON对象（AI可能在JSON前后添加说明文字）
            3. 解析失败抛出ValueError

        Args:
            content: AI返回的原始文本内容。

        Returns:
            解析后的用例数据字典。

        Raises:
            ValueError: 无法解析AI响应内容。
        """
        try:
            # 优先尝试直接JSON解析
            return json.loads(content)
        except json.JSONDecodeError:
            # AI可能在JSON前后添加了说明文字，尝试提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        raise ValueError("无法解析AI响应内容")

    async def _async_sleep(self, seconds: float) -> None:
        """异步休眠，用于重试间隔的指数退避。

        Args:
            seconds: 休眠秒数。
        """
        import asyncio
        await asyncio.sleep(seconds)
