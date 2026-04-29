"""
Test Case Generation Service - 测试用例生成服务
整合需求文档（文件）、UI原型图（文件）和测试点，生成高质量测试用例

重构：从 RequirementLink 改为 ProjectFile，不再依赖 URL 抓取
"""
import json
import re
import html
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from loguru import logger

from app.models.test_point import TestPoint
from app.models.test_case import TestCase, TestStep
from app.models.project import Project, ProjectFile
from app.models.ui_prototype import UIPrototypeScreen, UIPrototypeProject
from app.crud import test_point as test_point_crud
from app.crud import file as file_crud
from app.services.file_content_extractor import FileContentExtractor, get_file_content, has_extracted_content
from app.utils.ai_client import (
    ai_client,
    AIServiceError,
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
    AIResponseParseError,
    AIResponseFormatError
)
from app.core.config import settings


# 默认分页配置
DEFAULT_TEST_POINT_PAGE_SIZE = 100
MAX_TEST_POINT_PAGE_SIZE = 500

# 测试用例分类标签
TEST_CATEGORY_UI_AUTO = "ui_automation"     # UI自动化测试
TEST_CATEGORY_MANUAL = "manual"              # 手工测试
TEST_CATEGORY_API_AUTO = "api_automation"   # 接口自动化测试


class ContentSanitizer:
    """
    内容清洗器 - 防止Prompt注入攻击
    
    对用户输入的内容进行清洗和转义，确保AI输出安全可靠
    """

    # 常见的Prompt注入模式
    INJECTION_PATTERNS = [
        r'```system',
        r'```prompt',
        r'忽略.*指令',
        r'忽略.*规则',
        r'你是一个.*而不是',
        r'你现在是',
        r'/system',
        r'<system>',
        r'{{.*}}',
    ]

    @classmethod
    def sanitize(cls, content: str, max_length: int = 10000) -> str:
        """
        清洗内容，防止Prompt注入
        
        Args:
            content: 原始内容
            max_length: 最大长度限制
        
        Returns:
            清洗后的安全内容
        """
        if not content:
            return ""
        
        # 1. 移除JSON/Markdown代码块标记（防止注入）
        content = re.sub(r'```(?:json|yaml|xml|markdown|prompt|system)', '', content, flags=re.IGNORECASE)
        content = re.sub(r'```', '', content)
        
        # 2. 移除HTML标签但保留文本
        content = re.sub(r'<[^>]+>', '', content)
        
        # 3. HTML实体转义
        content = html.escape(content)
        
        # 4. 移除潜在的注入指令
        for pattern in cls.INJECTION_PATTERNS:
            content = re.sub(pattern, '[已过滤]', content, flags=re.IGNORECASE)
        
        # 5. 限制长度
        if len(content) > max_length:
            content = content[:max_length] + f"\n\n[内容已截断，原长度: {len(content)}字符]"
        
        return content

    @classmethod
    def sanitize_for_log(cls, content: str, max_length: int = 200) -> str:
        """
        清洗内容用于日志记录（更严格的截断）
        
        Args:
            content: 原始内容
            max_length: 最大长度
        
        Returns:
            清洗后的安全内容
        """
        if not content:
            return ""
        
        # 移除敏感信息和换行
        content = re.sub(r'[\n\r\t]+', ' ', content)
        
        if len(content) > max_length:
            return content[:max_length] + "..."
        
        return content


class TestCaseGenerationService:
    """
    测试用例生成服务
    
    主要功能：
    1. 获取需求文档内容（从链接缓存或实时获取）
    2. 获取UI原型图描述（通过视觉模型解析）
    3. 获取测试点信息（支持分页）
    4. 整合所有信息，调用AI生成高质量测试用例
    """

    def __init__(self, db: Session):
        self.db = db

    async def get_context_for_generation(
        self,
        project_id: int,
        user_id: int,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_ids: Optional[List[int]] = None,
        force_refresh: bool = False,
        test_point_page: int = 1,
        test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE
    ) -> Dict[str, Any]:
        """
        获取测试用例生成的上下文信息

        Args:
            project_id: 项目ID
            user_id: 用户ID
            requirement_file_ids: 需求文档文件ID列表
            ui_file_ids: UI原型图文件ID列表
            ui_screen_ids: UI原型屏幕ID列表（优先使用，包含解析后的ui_spec）
            test_point_ids: 测试点ID列表（优先）
            force_refresh: 是否强制刷新文件内容
            test_point_page: 测试点页码（当test_point_ids为空时生效）
            test_point_page_size: 测试点每页数量

        Returns:
            包含需求内容、UI描述、测试点的上下文字典
        """
        context = {
            "requirement_content": "",
            "ui_descriptions": [],
            "ui_specs": [],
            "test_points": [],
            "files_used": [],
            "warnings": [],
            "cache_info": {}
        }

        # 1. 获取需求文档内容
        if requirement_file_ids:
            for file_id in requirement_file_ids:
                file_record = file_crud.get_file_by_id(self.db, file_id, project_id)
                if file_record and file_record.resource_type == "requirement":
                    content = file_record.content or ""
                    if force_refresh or not content:
                        content = await get_file_content(file_id)
                    if content:
                        context["requirement_content"] += f"\n\n【{file_record.file_name}】\n{content}"
                        context["files_used"].append(file_id)

        # 如果没有指定需求文件，获取所有需求文件
        if not context["requirement_content"]:
            all_req_files = file_crud.get_project_files_by_type(self.db, project_id, "requirement")
            for file_record in all_req_files:
                content = file_record.content or ""
                if force_refresh or not content:
                    content = await get_file_content(file_record.id)
                if content:
                    context["requirement_content"] += f"\n\n【{file_record.file_name}】\n{content}"
                    context["files_used"].append(file_record.id)

        # 2. 获取UI原型图描述
        if ui_screen_ids:
            for screen_id in ui_screen_ids:
                screen = self.db.query(UIPrototypeScreen).filter(
                    UIPrototypeScreen.id == screen_id,
                    UIPrototypeScreen.project_id == project_id
                ).first()
                if screen:
                    ui_desc = {
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "prototype_name": screen.prototype_name,
                        "parse_status": screen.parse_status,
                        "summary": screen.summary or "",
                        "element_count": screen.element_count or 0,
                        "button_count": screen.button_count or 0,
                        "input_count": screen.input_count or 0,
                        "description": screen.summary or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    if screen.ui_spec:
                        context["ui_specs"].append({
                            "screen_id": screen.id,
                            "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })
        elif ui_file_ids:
            for file_id in ui_file_ids:
                file_record = file_crud.get_file_by_id(self.db, file_id, project_id)
                if file_record and file_record.resource_type == "ui_mockup":
                    ui_desc = {
                        "file_name": file_record.file_name,
                        "file_url": file_record.file_url,
                        "description": file_record.description or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    context["files_used"].append(file_id)

                    linked_screens = self.db.query(UIPrototypeScreen).filter(
                        UIPrototypeScreen.project_id == project_id,
                        UIPrototypeScreen.prototype_name == file_record.file_name,
                        UIPrototypeScreen.parse_status == "completed",
                        UIPrototypeScreen.ui_spec.isnot(None)
                    ).all()
                    for screen in linked_screens:
                        context["ui_specs"].append({
                            "screen_id": screen.id,
                            "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })

        if not context["ui_descriptions"] and not context["ui_specs"]:
            screens_with_spec = self.db.query(UIPrototypeScreen).filter(
                UIPrototypeScreen.project_id == project_id,
                UIPrototypeScreen.parse_status == "completed",
                UIPrototypeScreen.ui_spec.isnot(None)
            ).order_by(UIPrototypeScreen.screen_order).all()

            if screens_with_spec:
                for screen in screens_with_spec:
                    ui_desc = {
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "prototype_name": screen.prototype_name,
                        "parse_status": screen.parse_status,
                        "summary": screen.summary or "",
                        "element_count": screen.element_count or 0,
                        "button_count": screen.button_count or 0,
                        "input_count": screen.input_count or 0,
                        "description": screen.summary or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    if screen.ui_spec:
                        context["ui_specs"].append({
                            "screen_id": screen.id,
                            "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })
            else:
                all_ui_files = file_crud.get_project_files_by_type(self.db, project_id, "ui_mockup")
                for file_record in all_ui_files:
                    ui_desc = {
                        "file_name": file_record.file_name,
                        "file_url": file_record.file_url,
                        "description": file_record.description or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    context["files_used"].append(file_record.id)
        
        # 3. 获取测试点
        if test_point_ids:
            # 根据ID列表获取
            for point_id in test_point_ids:
                point = test_point_crud.get_test_point_by_id(self.db, point_id, project_id)
                if point:
                    context["test_points"].append({
                        "id": point.id,
                        "module": point.module,
                        "function": point.function,
                        "point": point.point,
                        "priority": point.priority
                    })
        else:
            # 分页获取所有测试点
            total_count = self.db.query(TestPoint).filter(
                TestPoint.project_id == project_id
            ).count()
            
            skip = (test_point_page - 1) * test_point_page_size
            all_points = self.db.query(TestPoint).filter(
                TestPoint.project_id == project_id
            ).order_by(TestPoint.priority.asc(), TestPoint.id.asc()).offset(skip).limit(
                min(test_point_page_size, MAX_TEST_POINT_PAGE_SIZE)
            ).all()
            
            for point in all_points:
                context["test_points"].append({
                    "id": point.id,
                    "module": point.module,
                    "function": point.function,
                    "point": point.point,
                    "priority": point.priority
                })
            
            # 添加分页信息
            context["pagination"] = {
                "page": test_point_page,
                "page_size": len(all_points),
                "total": total_count,
                "has_more": (test_point_page * test_point_page_size) < total_count
            }
        
        return context

    async def _get_file_content(self, file: ProjectFile, force_refresh: bool = False) -> Optional[str]:
        """获取文件内容（支持自动提取）"""
        # 如果文件已有提取的内容且不是强制刷新，直接返回
        if file.content and file.extract_status == 'completed' and not force_refresh:
            return file.content

        # 如果文件正在处理或没有内容，尝试提取
        if not file.content or file.extract_status in ['pending', 'failed']:
            extractor = FileContentExtractor(self.db)
            result = await extractor.extract_file_content(file, force_refresh)
            if result.get("success"):
                return result.get("content")

        return file.content  # 可能已有内容（即使过期）

    async def generate_test_case_for_point(
        self,
        context: Dict[str, Any],
        test_point: Dict[str, Any],
        project_id: int,
        case_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        为单个测试点生成测试用例

        Args:
            context: 上下文信息（需求内容、UI描述等）
            test_point: 测试点信息
            project_id: 项目ID
            case_type: 用例类型（可选，不指定时由AI智能判断）

        Returns:
            生成的测试用例

        Raises:
            AIServiceError: AI服务错误
        """
        # 构建UI描述文本
        ui_description = self._build_ui_description(context.get("ui_descriptions", []))

        # 清洗用户输入内容，防止Prompt注入
        requirement_content = ContentSanitizer.sanitize(
            context.get("requirement_content", "")
        )
        ui_description = ContentSanitizer.sanitize(ui_description)

        # 调用AI生成测试用例
        # 根据是否有UI原型图和文件内容来决定测试用例分类标签
        has_ui = bool(ui_description and ui_description.strip()) or bool(context.get("ui_specs", []))
        has_requirement = bool(requirement_content and requirement_content.strip())

        if not has_ui:
            # 没有UI原型图，生成手工测试用例
            case_category = TEST_CATEGORY_MANUAL
        else:
            # 有UI原型图，根据UI描述判断是否可以自动化
            # 如果UI描述包含按钮、表单、输入框等可交互元素，则标记为UI自动化
            ui_keywords = ['按钮', '表单', '输入框', '下拉框', '复选框', '单选框', '链接', '导航',
                          'button', 'input', 'form', 'dropdown', 'checkbox', 'radio', 'link', 'menu']
            ui_has_interactive = any(k in ui_description.lower() for k in ui_keywords)
            case_category = TEST_CATEGORY_UI_AUTO if ui_has_interactive else TEST_CATEGORY_MANUAL

        generation_context = {
            "requirement_content": requirement_content,
            "ui_description": ui_description,
            "ui_specs": context.get("ui_specs", []),
            "test_point": test_point,
            "case_type": case_type if case_type else "ui_automation",
            "case_category": case_type if case_type else case_category
        }

        # 直接调用，不再捕获异常返回假数据
        # 异常会向上传播，由调用者处理
        generated_case = await self._generate_case_with_ai(generation_context)
        return generated_case

    async def _generate_case_with_ai(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用AI生成测试用例

        Args:
            context: 生成上下文

        Returns:
            生成的测试用例
        """
        import httpx

        requirement_content = context.get("requirement_content", "")
        ui_description = context.get("ui_description", "")
        ui_specs = context.get("ui_specs", [])
        test_point = context.get("test_point", {})

        module = test_point.get("module", "未知模块")
        function = test_point.get("function", "未知功能")
        point = test_point.get("point", "")
        priority = test_point.get("priority", 2)

        prompt = self._build_generation_prompt(
            requirement_content=requirement_content,
            ui_description=ui_description,
            module=module,
            function=function,
            point=point,
            priority=priority,
            ui_specs=ui_specs
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"
        }

        payload = {
            "model": settings.DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 3000
        }

        # 使用异步HTTP调用，带重试机制
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                    response = await client.post(
                        settings.DEEPSEEK_API_URL,
                        headers=headers,
                        json=payload
                    )
                    response.raise_for_status()

                    result = response.json()

                    # 防御性检查：验证API响应结构
                    if "choices" not in result:
                        logger.error("AI API响应缺少choices字段")
                        raise ValueError("AI API响应格式错误：缺少choices字段")

                    choices = result["choices"]
                    if not choices or len(choices) == 0:
                        logger.error("AI API返回空choices")
                        raise ValueError("AI API返回结果为空")

                    first_choice = choices[0]
                    if "message" not in first_choice:
                        logger.error("AI API响应choices[0]缺少message字段")
                        raise ValueError("AI响应格式错误：缺少message字段")

                    message = first_choice["message"]
                    content = message.get("content", "")

                    if not content:
                        logger.error("AI响应内容为空")
                        raise ValueError("AI响应内容为空")

                    # 提取JSON
                    generated_case = self._parse_ai_response(content)
                    return generated_case

            except httpx.TimeoutException as e:
                last_error = f"AI API请求超时 (尝试 {attempt + 1}/{max_retries})"
                logger.warning(last_error)
                if attempt < max_retries - 1:
                    await self._async_sleep(2 ** attempt)  # 指数退避
            except httpx.HTTPStatusError as e:
                last_error = f"AI API HTTP错误: {e.response.status_code}"
                logger.error(last_error)
                if attempt < max_retries - 1:
                    await self._async_sleep(2 ** attempt)
            except httpx.RequestError as e:
                last_error = f"AI API请求错误: {str(e)}"
                logger.error(last_error)
                if attempt < max_retries - 1:
                    await self._async_sleep(2 ** attempt)
            except (ValueError, json.JSONDecodeError) as e:
                last_error = f"AI响应解析失败: {str(e)}"
                logger.error(last_error)
                raise

        # 所有重试都失败
        logger.error(f"AI生成失败，已重试{max_retries}次: {last_error}")
        raise ValueError(f"AI生成失败: {last_error}")

    def _build_generation_prompt(
        self,
        requirement_content: str,
        ui_description: str,
        module: str,
        function: str,
        point: str,
        priority: int,
        ui_specs: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        构建AI生成提示词（结构化方式）
        
        使用更安全的结构化输入，减少Prompt注入风险
        """
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

        ui_section = ""
        if ui_spec_text:
            ui_section = f"""## UI原型图解析结果（验收标准，优先参考）：
{ui_spec_text}"""
        elif ui_description and ui_description.strip():
            ui_section = f"""## UI原型图描述：
{ui_description}"""
        else:
            ui_section = "## UI原型图描述：[无UI原型图信息]"

        test_point_json = json.dumps({
            "module": module,
            "function": function,
            "point": point,
            "priority": priority
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
        """将ui_spec格式化为AI可理解的文本描述"""
        parts = [f"【页面：{screen_name}】"]

        if ui_spec.get('purpose'):
            parts.append(f"页面功能：{ui_spec['purpose']}")

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

        navigation = ui_spec.get('navigation', {})
        if navigation:
            parts.append("导航结构：")
            for nav_key, nav_val in navigation.items():
                if nav_val:
                    parts.append(f"  - {nav_key}: {nav_val}")

        layout_checks = ui_spec.get('layout_constraints', [])
        if layout_checks:
            parts.append(f"布局约束（共{len(layout_checks)}项）：")
            for check in layout_checks[:10]:
                desc = check.get('description', '')
                if desc:
                    parts.append(f"  - {desc}")

        flows = ui_spec.get('flows', {})
        if flows:
            next_screens = flows.get('expected_next_screens', [])
            if next_screens:
                parts.append(f"预期跳转页面：{', '.join(next_screens)}")

        return "\n".join(parts)

    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """
        解析AI响应内容
        
        Args:
            content: AI返回的原始内容
        
        Returns:
            解析后的测试用例字典
        """
        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取JSON块
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        
        raise ValueError("无法解析AI响应内容")

    async def _async_sleep(self, seconds: float):
        """异步睡眠"""
        import asyncio
        await asyncio.sleep(seconds)

    def _build_ui_description(self, ui_descriptions: List[Dict[str, Any]]) -> str:
        """
        构建UI描述文本

        Args:
            ui_descriptions: UI描述列表（来自 ProjectFile 或 UIPrototypeScreen）

        Returns:
            UI描述文本
        """
        if not ui_descriptions:
            return ""

        parts = []
        for ui_desc in ui_descriptions:
            if ui_desc.get("screen_name"):
                name = ui_desc["screen_name"]
                summary = ui_desc.get("summary", "")
                element_count = ui_desc.get("element_count", 0)
                button_count = ui_desc.get("button_count", 0)
                input_count = ui_desc.get("input_count", 0)
                desc_parts = [f"【{name}】"]
                if summary:
                    desc_parts.append(f"功能：{summary}")
                if element_count:
                    desc_parts.append(f"元素：{element_count}个（按钮{button_count}个，输入框{input_count}个）")
                parts.append("\n".join(desc_parts))
            else:
                name = ui_desc.get("screen_name") or ui_desc.get("file_name") or ui_desc.get("name", "未命名")
                file_id = ui_desc.get("file_id", "")
                content = ui_desc.get("content", "")
                description = ui_desc.get("description", "")

                if content:
                    parts.append(f"【{name}】\n{content}")
                elif description:
                    parts.append(f"【{name}】\n{description}")
                else:
                    parts.append(f"【{name}】(文件ID: {file_id}，内容待提取)")

        return "\n\n".join(parts)

    def _get_default_case(self, test_point: Dict[str, Any]) -> Dict[str, Any]:
        """获取默认测试用例（已废弃，不再使用）

        警告: 此方法已废弃，不再用于AI调用失败时的fallback。
        如果AI调用失败，应抛出异常而不是返回假数据。
        此方法保留仅为避免代码破坏性变更，但不应被调用。
        """
        logger.error("调用了已废弃的 _get_default_case 方法，不应发生！")
        raise AIServiceError("AI生成失败，无法返回默认测试用例")

    async def generate_test_cases_batch(
        self,
        project_id: int,
        user_id: int,
        test_point_ids: Optional[List[int]] = None,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_page: int = 1,
        test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE,
        case_type: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        批量生成测试用例

        Args:
            project_id: 项目ID
            user_id: 用户ID
            test_point_ids: 测试点ID列表
            requirement_file_ids: 需求文档文件ID列表
            ui_file_ids: UI原型图文件ID列表
            test_point_page: 测试点页码
            test_point_page_size: 测试点每页数量
            case_type: 用例类型（可选，不指定时由AI智能判断）

        Yields:
            生成进度和结果
        """
        # 获取上下文信息
        yield {"progress": 5, "message": "获取上下文信息", "status": "running"}

        context = await self.get_context_for_generation(
            project_id=project_id,
            user_id=user_id,
            requirement_file_ids=requirement_file_ids,
            ui_file_ids=ui_file_ids,
            ui_screen_ids=ui_screen_ids,
            test_point_ids=test_point_ids,
            test_point_page=test_point_page,
            test_point_page_size=test_point_page_size
        )
        
        # 报告警告信息
        warnings = context.get("warnings", [])
        if warnings:
            for warning in warnings[:3]:  # 最多报告3个警告
                yield {"progress": 5, "message": warning, "status": "warning"}
        
        test_points = context.get("test_points", [])
        total = len(test_points)
        
        if total == 0:
            yield {"progress": 100, "message": "没有找到测试点", "status": "warning", "data": []}
            return
        
        # 检查是否有分页
        pagination = context.get("pagination", {})
        
        yield {
            "progress": 10,
            "message": f"开始生成{total}个测试用例",
            "status": "running",
            "total": total,
            "pagination": pagination
        }
        
        created_cases = []
        failed_count = 0
        
        # 获取第一个需求文件ID（如果有）用于关联
        primary_requirement_file_id = requirement_file_ids[0] if requirement_file_ids else None
        
        for i, test_point in enumerate(test_points):
            try:
                # 生成测试用例
                generated_case = await self.generate_test_case_for_point(
                    context=context,
                    test_point=test_point,
                    project_id=project_id,
                    case_type=case_type
                )
                
                # 保存到数据库，关联需求文件
                case = await self._save_test_case(
                    project_id=project_id,
                    generated_case=generated_case,
                    test_point=test_point,
                    requirement_file_id=primary_requirement_file_id
                )
                created_cases.append(case)
                
                progress = int(10 + (i + 1) / total * 85)
                yield {
                    "progress": progress,
                    "message": f"已生成{i + 1}/{total}个测试用例",
                    "status": "running",
                    "current": i + 1,
                    "total": total,
                    "case": {
                        "id": case.id,
                        "title": ContentSanitizer.sanitize_for_log(case.title),
                        "module": case.module
                    }
                }
                
            except Exception as e:
                failed_count += 1
                logger.error(f"生成测试用例失败: {e}")
                yield {
                    "progress": int(10 + (i + 1) / total * 85),
                    "message": f"生成第{i + 1}个用例失败: {str(e)}",
                    "status": "running",
                    "error": True,
                    "failed_count": failed_count
                }
        
        yield {
            "progress": 100,
            "message": f"完成！成功{len(created_cases)}个，失败{failed_count}个",
            "status": "success" if failed_count == 0 else "partial",
            "total": total,
            "created": len(created_cases),
            "failed": failed_count,
            "pagination": pagination,
            "cases": [
                {"id": c.id, "title": ContentSanitizer.sanitize_for_log(c.title)}
                for c in created_cases
            ]
        }

    async def _save_test_case(
        self,
        project_id: int,
        generated_case: Dict[str, Any],
        test_point: Dict[str, Any],
        requirement_file_id: Optional[int] = None
    ) -> TestCase:
        """
        保存测试用例到数据库
        
        Args:
            project_id: 项目ID
            generated_case: 生成的用例数据
            test_point: 来源测试点
            requirement_file_id: 关联的需求文件ID（可选）
        
        Returns:
            保存的测试用例对象
        """
        # 生成用例编号
        case_no = f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # 构建步骤数据
        steps = generated_case.get("steps", [])
        steps_json = []
        for i, step in enumerate(steps):
            steps_json.append({
                "step": step.get("step", str(i + 1)),
                "description": step.get("description", ""),
                "action": step.get("action", "执行"),
                "expected_result": step.get("expected_result", ""),
                "param": step.get("param", "")
            })

        # 创建测试用例
        test_case = TestCase(
            project_id=project_id,
            requirement_file_id=requirement_file_id,
            case_no=case_no,
            module=generated_case.get("module", test_point.get("module", "AI生成")),
            title=generated_case.get("title", test_point.get("function", "测试用例")),
            precondition=generated_case.get("precondition", ""),
            steps_json=steps_json,
            expected_result=generated_case.get("expected_result", ""),
            priority=generated_case.get("priority", test_point.get("priority", 2)),
            case_type=generated_case.get("case_type") or generated_case.get("test_category") or "manual",
            test_category=generated_case.get("case_category", TEST_CATEGORY_MANUAL),
            generate_status=1
        )

        self.db.add(test_case)
        self.db.flush()

        # 创建测试步骤
        for i, step in enumerate(steps):
            test_step = TestStep(
                test_case_id=test_case.id,
                step_number=i + 1,
                action=step.get("action", step.get("description", step.get("step", "执行"))),
                expected_result=step.get("expected_result", step.get("param", "预期结果正常")),
                is_business_view=1,
                is_technical_view=1
            )
            self.db.add(test_step)
        
        self.db.commit()
        self.db.refresh(test_case)
        
        if settings.AUTO_PARSE_PRECONDITION and test_case.precondition and test_case.precondition.strip():
            try:
                from app.utils.ai_client import parse_precondition_to_steps
                from app.models.test_case import TestCasePreconditionStep
                
                project = self.db.query(Project).filter(Project.id == project_id).first()
                project_url = ""
                if project:
                    project_url = getattr(project, 'test_object_url', '') or ''
                
                parsed_steps = await parse_precondition_to_steps(
                    precondition_text=test_case.precondition,
                    project_url=project_url
                )
                
                if parsed_steps:
                    for idx, step_data in enumerate(parsed_steps):
                        pc_step = TestCasePreconditionStep(
                            test_case_id=test_case.id,
                            step_number=idx + 1,
                            action=step_data.get("action", ""),
                            action_type=step_data.get("action_type", "click"),
                            input_value=step_data.get("input_value", ""),
                            target_element=step_data.get("target_element", ""),
                            expected_result=step_data.get("expected_result", ""),
                            has_locator=0,
                            locator_status="pending"
                        )
                        self.db.add(pc_step)
                    self.db.commit()
                    logger.info(f"自动解析前置条件成功，生成 {len(parsed_steps)} 个步骤 (用例ID={test_case.id})")
            except Exception as e:
                logger.warning(f"自动解析前置条件失败 (用例ID={test_case.id}): {e}")
        
        return test_case


# 全局便捷函数
async def get_test_case_context(
    db: Session,
    project_id: int,
    user_id: int,
    requirement_file_ids: Optional[List[int]] = None,
    ui_file_ids: Optional[List[int]] = None,
    ui_screen_ids: Optional[List[int]] = None,
    test_point_ids: Optional[List[int]] = None,
    test_point_page: int = 1,
    test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE
) -> Dict[str, Any]:
    """获取测试用例生成的上下文"""
    service = TestCaseGenerationService(db)
    return await service.get_context_for_generation(
        project_id=project_id,
        user_id=user_id,
        requirement_file_ids=requirement_file_ids,
        ui_file_ids=ui_file_ids,
        ui_screen_ids=ui_screen_ids,
        test_point_ids=test_point_ids,
        test_point_page=test_point_page,
        test_point_page_size=test_point_page_size
    )
