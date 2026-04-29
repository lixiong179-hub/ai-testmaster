"""
元素定位服务

提供元素定位记录、CSS选择器生成、定位信息查询等功能
"""
import json
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.utils.db_time import utcnow
from contextlib import contextmanager
from sqlalchemy.orm import Session
from loguru import logger

from app.models.element_locator import ElementLocator
from app.models.enums import LocatorStatus
from app.models.test_case import TestStep, TestCasePreconditionStep
from app.services.selector_registry import SelectorRegistry
from app.utils.browser_controller import BrowserController
from app.utils.unified_vision_model import UnifiedVisionModel
from app.interfaces.element_recognizer import ElementRecognizer, RecognitionResult
from app.services.recognizers.vision_recognizer import VisionRecognizer
from app.services.recognizers.mcp_recognizer import MCPRecognizer
from app.core.config import settings


class ElementLocatorService:
    """
    元素定位服务
    
    功能：
    - 记录元素定位信息（CSS选择器、XPath、AI坐标等）
    - 自动生成CSS选择器
    - 查询历史定位信息
    - 更新定位使用统计
    - 智能元素定位（CSS选择器优先，AI视觉辅助）
    """
    
    MIN_CONFIDENCE_THRESHOLD = 0.8
    MAX_CLASS_COUNT = 2
    MAX_TEXT_LENGTH = 20
    MAX_PLACEHOLDER_LENGTH = 10
    MAX_ELEMENT_TEXT_LENGTH = 100
    
    def __init__(self, db: Session, browser: BrowserController, vision_model: UnifiedVisionModel, confidence_threshold: Optional[float] = None, recognizer: Optional[ElementRecognizer] = None):
        self.db = db
        self.browser = browser
        self.vision_model = vision_model
        self.confidence_threshold = confidence_threshold or self.MIN_CONFIDENCE_THRESHOLD
        self.recognizer = recognizer or self._create_default_recognizer()

    def _create_default_recognizer(self) -> ElementRecognizer:
        if getattr(settings, 'PLAYWRIGHT_MCP_ENABLED', False):
            return MCPRecognizer()
        return VisionRecognizer(self.vision_model, self.confidence_threshold)

    @classmethod
    def create_locator_service(cls, db: Session, browser: BrowserController, vision_model: UnifiedVisionModel, confidence_threshold: Optional[float] = None, use_mcp: Optional[bool] = None) -> 'ElementLocatorService':
        if use_mcp is None:
            use_mcp = getattr(settings, 'PLAYWRIGHT_MCP_ENABLED', False)
        recognizer = MCPRecognizer() if use_mcp else VisionRecognizer(vision_model, confidence_threshold or cls.MIN_CONFIDENCE_THRESHOLD)
        return cls(db, browser, vision_model, confidence_threshold, recognizer=recognizer)

    @contextmanager
    def transaction(self):
        """数据库事务上下文管理器"""
        try:
            yield
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"数据库事务失败: {str(e)}")
            raise
    
    def get_locator(self, step_id: int) -> Optional[ElementLocator]:
        """
        获取步骤的元素定位信息
        
        Args:
            step_id: 测试步骤ID
            
        Returns:
            元素定位信息，不存在返回None
        """
        return self.db.query(ElementLocator).filter(
            ElementLocator.step_id == step_id
        ).first()
    
    def has_locator(self, step_id: int) -> bool:
        """
        检查步骤是否有元素定位信息
        
        Args:
            step_id: 测试步骤ID
            
        Returns:
            是否有定位信息
        """
        return self.get_locator(step_id) is not None
    
    async def smart_locate_element(
        self,
        action_description: str,
        page_title: Optional[str] = None,
        action_type: Optional[str] = None,
        input_value: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        logger.info(f"智能定位元素: {action_description}")

        registry = SelectorRegistry()
        css_selector = registry.get_selector(page_title, action_description)

        if css_selector:
            logger.info(f"使用预定义选择器: {css_selector}")
            try:
                first_selector = css_selector.split(',')[0].strip()
                element_exists = await self.browser.execute_javascript("""
                    (function() {
                        return document.querySelector(arguments[0]) !== null;
                    })()
                """, first_selector)

                if element_exists:
                    element_info = await self.browser.execute_javascript("""
                        (function() {
                            var el = document.querySelector(arguments[0]);
                            if (el) {
                                var rect = el.getBoundingClientRect();
                                return {
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height,
                                    css_selector: arguments[1],
                                    confidence: 0.95
                                };
                            }
                            return null;
                        })()
                    """, first_selector, css_selector)

                    if element_info:
                        logger.info(f"预定义选择器定位成功: {element_info}")
                        return element_info
            except Exception as e:
                logger.warning(f"预定义选择器失败: {e}")

        logger.info(f"预定义选择器失败，使用{self.recognizer.name}识别器")
        recognition_result = await self.recognizer.recognize(self.browser, action_description, action_type=action_type)

        if recognition_result and recognition_result.is_valid:
            if recognition_result.locator_type == "vision" and recognition_result.element_info:
                element_info = recognition_result.element_info
                if element_info.get("css_selector"):
                    logger.info(f"AI视觉定位成功: {element_info}")
                    return element_info
                element_attrs = await self._get_element_attributes(element_info)
                css_selector = self._generate_css_selector(element_attrs)
                element_info['css_selector'] = css_selector
                logger.info(f"AI视觉定位成功: {element_info}")
                return element_info
            elif recognition_result.locator_type in ("role", "text", "css", "ref"):
                result_info = {
                    "locator_type": recognition_result.locator_type,
                    "locator_value": recognition_result.locator_value,
                    "confidence": recognition_result.confidence,
                    "css_selector": recognition_result.locator_value if recognition_result.locator_type == "css" else None
                }
                if recognition_result.element_info:
                    result_info.update(recognition_result.element_info)
                if action_type and self._should_direct_execute(action_type):
                    executed = await self.direct_execute_action(recognition_result, action_type, input_value)
                    if executed:
                        result_info["_direct_executed"] = True
                logger.info(f"MCP定位成功: {result_info}")
                return result_info

        logger.error(f"无法定位元素: {action_description}")
        return None

    def _should_direct_execute(self, action_type: str) -> bool:
        if not getattr(settings, 'MCP_DIRECT_EXECUTION_ENABLED', False):
            return False
        if not isinstance(self.recognizer, MCPRecognizer):
            return False
        allowed_types = getattr(settings, 'MCP_EXECUTION_OPERATION_TYPES', 'click,type,hover,select').split(',')
        return action_type in allowed_types

    async def direct_execute_action(self, recognition_result: RecognitionResult, action_type: str = "click", input_value: Optional[str] = None) -> bool:
        if not isinstance(self.recognizer, MCPRecognizer):
            return False
        try:
            return await self.recognizer.execute_action(recognition_result, action_type, input_value)
        except Exception as e:
            logger.warning(f"MCP直执失败: {e}")
            return False
    
    async def record_locator(
        self,
        step_id: int,
        action_description: str,
        screenshot: Optional[bytes] = None,
        source: str = "ai"
    ) -> Optional[ElementLocator]:
        """
        记录元素定位信息
        
        流程：
        1. AI识别目标元素坐标
        2. 通过JavaScript获取元素属性
        3. 生成CSS选择器
        4. 保存到数据库
        
        Args:
            step_id: 测试步骤ID
            action_description: 操作描述（如"点击登录按钮"）
            screenshot: 页面截图（可选，不传则自动截取）
            
        Returns:
            保存的元素定位信息
        """
        logger.info(f"开始记录步骤 {step_id} 的元素定位信息")
        
        # 1. 截取页面截图
        if screenshot is None:
            screenshot = await self.browser.take_screenshot()
        
        # 2. AI识别目标元素
        element_info = await self.recognizer.recognize(self.browser, action_description)
        element_info = element_info.element_info if element_info and element_info.is_valid else None
        if not element_info:
            logger.warning(f"步骤 {step_id}: AI无法识别目标元素")
            return None
        
        logger.info(f"步骤 {step_id}: AI识别到元素坐标: {element_info}")
        
        # 3. 通过JavaScript获取元素属性
        element_attrs = await self._get_element_attributes(element_info)
        logger.info(f"步骤 {step_id}: 获取到元素属性: {element_attrs}")
        
        # 4. 生成CSS选择器
        css_selector = self._generate_css_selector(element_attrs)
        logger.info(f"步骤 {step_id}: 生成CSS选择器: {css_selector}")

        coordinate = self._normalize_coordinate(element_info)

        locator = ElementLocator(
            step_id=step_id,
            element_description=action_description,
            element_type=element_attrs.get("tag"),
            css_selector=css_selector,
            xpath=self._generate_xpath(element_attrs),
            element_id=element_attrs.get("id"),
            element_name=element_attrs.get("name"),
            element_class=element_attrs.get("class"),
            element_text=element_attrs.get("text"),
            ai_coordinate=coordinate,
            ai_confidence=element_info.get("confidence", 0),
            source=source
        )
        
        self.db.add(locator)
        self.db.commit()
        self.db.refresh(locator)

        step = self.db.query(TestStep).filter(TestStep.id == step_id).first()
        if step:
            step.has_locator = 1
            step.locator_status = LocatorStatus.RECORDED.value
            self.db.commit()

        logger.info(f"步骤 {step_id}: 元素定位信息已保存，ID={locator.id}")
        return locator
    
    async def record_precondition_step_locator(
        self,
        precondition_step_id: int,
        action_description: str,
        action_type: Optional[str] = None,
        screenshot: Optional[bytes] = None
    ) -> Optional[ElementLocator]:
        """
        记录前置条件步骤的元素定位信息
        
        与 record_locator 不同，此方法使用 precondition_step_id 关联 ElementLocator，
        而非 step_id。前置条件步骤不关联 test_steps 表。
        
        Args:
            precondition_step_id: 前置条件步骤ID
            action_description: 操作描述
            action_type: 操作类型（可选）
            screenshot: 页面截图（可选，不传则自动截取）
            
        Returns:
            保存的元素定位信息
        """
        logger.info(f"开始记录前置条件步骤 {precondition_step_id} 的元素定位信息")
        
        if screenshot is None:
            screenshot = await self.browser.take_screenshot()
        
        recognition_result = await self.recognizer.recognize(self.browser, action_description, action_type=action_type)
        element_info = recognition_result.element_info if recognition_result and recognition_result.is_valid else None
        if not element_info:
            logger.warning(f"前置条件步骤 {precondition_step_id}: AI无法识别目标元素")
            return None
        
        element_attrs = await self._get_element_attributes(element_info)
        css_selector = self._generate_css_selector(element_attrs)
        coordinate = self._normalize_coordinate(element_info)
        
        locator = ElementLocator(
            step_id=None,
            precondition_step_id=precondition_step_id,
            element_description=action_description,
            element_type=element_attrs.get("tag"),
            css_selector=css_selector,
            xpath=self._generate_xpath(element_attrs),
            element_id=element_attrs.get("id"),
            element_name=element_attrs.get("name"),
            element_class=element_attrs.get("class"),
            element_text=element_attrs.get("text"),
            ai_coordinate=coordinate,
            ai_confidence=element_info.get("confidence", 0),
            source="ai"
        )
        
        self.db.add(locator)
        self.db.commit()
        self.db.refresh(locator)
        
        pc_step = self.db.query(TestCasePreconditionStep).filter(
            TestCasePreconditionStep.id == precondition_step_id
        ).first()
        if pc_step:
            pc_step.has_locator = 1
            pc_step.locator_status = LocatorStatus.RECORDED.value
            self.db.commit()
        
        logger.info(f"前置条件步骤 {precondition_step_id}: 元素定位信息已保存，ID={locator.id}")
        return locator
    
    async def _recognize_element(
        self,
        screenshot: bytes,
        action_description: str,
        action_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        logger.warning("_recognize_element已废弃，请使用recognizer.recognize()")
        if isinstance(self.recognizer, VisionRecognizer):
            result = await self.recognizer.recognize(self.browser, action_description, action_type)
        else:
            vision_recognizer = VisionRecognizer(self.vision_model, self.confidence_threshold)
            result = await vision_recognizer.recognize(self.browser, action_description, action_type)
        if result and result.is_valid:
            return result.element_info
        return None

    def _build_recognition_prompt(self, action_description: str, action_type: Optional[str] = None) -> str:
        base_prompt = f"请仔细分析这个页面截图，精确定位以下操作的目标元素：\n\n操作描述: {action_description}\n\n"

        login_keywords = ["登录", "用户名", "密码", "验证码", "login", "username", "password"]
        is_login_page = any(kw in action_description.lower() for kw in login_keywords)

        if is_login_page:
            base_prompt += """重要提示：
1. 这是一个登录表单页面，包含多个输入框（用户名、密码、验证码）
2. 请根据操作描述中的关键词，准确找到对应的输入框
3. 用户名输入框通常有"用户名"标签或用户图标
4. 密码输入框通常有"密码"标签或锁图标，输入内容会显示为圆点
5. 验证码输入框通常在验证码图片旁边

"""
        else:
            base_prompt += """请根据操作描述中的关键词，在页面中找到对应的目标元素。
注意区分相似元素，确保选择正确的目标。

"""

        if action_type == "verify":
            base_prompt += """这是一个验证步骤，请定位需要验证的目标元素的位置和状态。
重点关注元素的显示文本和位置。

"""

        base_prompt += f"""请返回JSON格式：
{{
    "x": 元素左上角x坐标（整数）,
    "y": 元素左上角y坐标（整数）,
    "width": 元素宽度（整数）,
    "height": 元素高度（整数）,
    "element_type": "input|button|text",
    "placeholder": "placeholder文本或标签文本",
    "confidence": 识别置信度(0-1),
    "reasoning": "为什么选择了这个元素"
}}

注意：
- x, y 是相对于截图左上角的像素坐标
- 坐标必须是整数，不能是数组
- 如果无法识别，返回 null
- 必须根据操作描述精确匹配对应的元素，不要混淆
"""
        return base_prompt
    
    async def _get_element_attributes(
        self,
        element_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        通过JavaScript获取元素属性
        
        Args:
            element_info: 元素坐标信息
            
        Returns:
            元素属性（id、class、name等）
        """
        x = element_info.get("x", 0) + element_info.get("width", 0) // 2
        y = element_info.get("y", 0) + element_info.get("height", 0) // 2
        
        js_code = """
        (function() {
            var element = document.elementFromPoint(arguments[0], arguments[1]);
            if (!element) return null;
            
            return {
                tag: element.tagName.toLowerCase(),
                id: element.id || null,
                name: element.getAttribute('name') || null,
                class: element.className || null,
                text: element.textContent ? element.textContent.trim().substring(0, 100) : null,
                'data-testid': element.getAttribute('data-testid') || null,
                'data-id': element.getAttribute('data-id') || null,
                type: element.getAttribute('type') || null,
                placeholder: element.getAttribute('placeholder') || null
            };
        })()
        """
        
        try:
            attrs = await self.browser.execute_javascript(js_code, x, y)
            return attrs or {}
        except TimeoutError as e:
            logger.error(f"获取元素属性超时: {str(e)}")
            return {}
        except ConnectionError as e:
            logger.error(f"浏览器连接失败: {str(e)}")
            return {}
        except Exception as e:
            logger.exception(f"获取元素属性发生未知错误: {str(e)}")
            return {}
    
    @staticmethod
    def _normalize_coordinate(element_info: Dict[str, Any], inplace: bool = False) -> Dict[str, Any]:
        """
        规范化坐标信息，处理缺失值和列表类型

        Args:
            element_info: 包含坐标信息的字典
            inplace: 是否原地修改element_info

        Returns:
            规范化后的坐标字典
        """
        result = element_info if inplace else {}
        for key in ["x", "y", "width", "height"]:
            val = element_info.get(key, 0)
            if val is None:
                val = 0
            if isinstance(val, list):
                val = val[0] if val else 0
            result[key] = val
        return result

    def _sanitize_for_css(self, value: str) -> str:
        r"""
        清理CSS选择器中的特殊字符
        
        CSS选择器中的特殊字符需要转义：!"#$%&'()*+,./:;<=>?@[\]^`{|}~
        
        Args:
            value: 原始值
            
        Returns:
            转义后的安全值
        """
        if not value:
            return ""
        # 转义CSS特殊字符
        special_chars = r'([!"#$%&\'()*+,./:;<=>?@[\\\]^`{|}~])'
        return re.sub(special_chars, r'\\\1', value)
    
    def _sanitize_for_xpath(self, value: str) -> str:
        """
        清理XPath中的特殊字符
        
        处理XPath字符串中的引号问题
        
        Args:
            value: 原始值
            
        Returns:
            安全的XPath字符串
        """
        if not value:
            return ""
        # 如果同时包含单双引号，使用concat
        if '"' in value and "'" in value:
            parts = value.split('"')
            return 'concat("' + '", \'"\', "'.join(parts) + '")'
        elif '"' in value:
            return f"'{value}'"
        else:
            return f'"{value}"'
    
    def _generate_css_selector(self, element_attrs: Dict[str, Any]) -> Optional[str]:
        """
        基于元素属性生成CSS选择器
        
        策略（按优先级）：
        1. #id（最稳定）
        2. [data-testid="xxx"]（推荐用于测试）
        3. tag.class（次选）
        4. tag[attr="value"]（备选）
        
        Args:
            element_attrs: 元素属性
            
        Returns:
            CSS选择器
        """
        tag = element_attrs.get("tag", "")
        element_id = element_attrs.get("id")
        data_testid = element_attrs.get("data-testid")
        element_class = element_attrs.get("class")
        element_name = element_attrs.get("name")
        element_type = element_attrs.get("type")
        placeholder = element_attrs.get("placeholder")
        
        # 1. 如果有id，使用 #id（最稳定）
        if element_id:
            safe_id = self._sanitize_for_css(element_id)
            return f"#{safe_id}"
        
        # 2. 如果有data-testid，使用 [data-testid="xxx"]（推荐）
        if data_testid:
            safe_testid = self._sanitize_for_css(data_testid)
            return f"[data-testid='{safe_testid}']"
        
        # 3. 如果有name属性，使用 [name="xxx"]
        if element_name:
            safe_name = self._sanitize_for_css(element_name)
            return f"[name='{safe_name}']"
        
        # 4. 如果有class，使用 tag.class1.class2（最多2个class）
        if element_class:
            classes = element_class.split()[:self.MAX_CLASS_COUNT]
            safe_classes = [self._sanitize_for_css(c) for c in classes]
            class_selector = ".".join(safe_classes)
            safe_tag = self._sanitize_for_css(tag)
            return f"{safe_tag}.{class_selector}"
        
        # 5. 如果有type和placeholder，使用组合
        if element_type and placeholder:
            safe_tag = self._sanitize_for_css(tag)
            safe_type = self._sanitize_for_css(element_type)
            safe_placeholder = self._sanitize_for_css(placeholder[:self.MAX_PLACEHOLDER_LENGTH])
            return f"{safe_tag}[type='{safe_type}'][placeholder*='{safe_placeholder}']"
        
        # 6. 如果只有type
        if element_type:
            safe_tag = self._sanitize_for_css(tag)
            safe_type = self._sanitize_for_css(element_type)
            return f"{safe_tag}[type='{safe_type}']"
        
        # 7. 最后使用tag
        safe_tag = self._sanitize_for_css(tag)
        return safe_tag if safe_tag else None
    
    def _generate_xpath(self, element_attrs: Dict[str, Any]) -> Optional[str]:
        """
        基于元素属性生成XPath
        
        Args:
            element_attrs: 元素属性
            
        Returns:
            XPath
        """
        tag = element_attrs.get("tag", "*")
        element_id = element_attrs.get("id")
        element_name = element_attrs.get("name")
        element_text = element_attrs.get("text")
        
        # 1. 如果有id，使用 //tag[@id='xxx']
        if element_id:
            safe_tag = self._sanitize_for_xpath(tag).strip('"\'')
            safe_id = self._sanitize_for_xpath(element_id)
            return f"//{safe_tag}[@id={safe_id}]"
        
        # 2. 如果有name，使用 //tag[@name='xxx']
        if element_name:
            safe_tag = self._sanitize_for_xpath(tag).strip('"\'')
            safe_name = self._sanitize_for_xpath(element_name)
            return f"//{safe_tag}[@name={safe_name}]"
        
        # 3. 如果有text，使用 //tag[contains(text(),'xxx')]
        if element_text:
            safe_tag = self._sanitize_for_xpath(tag).strip('"\'')
            text = element_text[:self.MAX_TEXT_LENGTH]
            safe_text = self._sanitize_for_xpath(text)
            return f"//{safe_tag}[contains(text(),{safe_text})]"
        
        safe_tag = self._sanitize_for_xpath(tag).strip('"\'')
        return f"//{safe_tag}"
    
    def record_locator_success(self, step_id: int) -> None:
        """
        记录定位成功
        
        Args:
            step_id: 测试步骤ID
        """
        locator = self.get_locator(step_id)
        if locator:
            locator.record_success()
            self.db.commit()
            logger.debug(f"步骤 {step_id}: 记录定位成功")
    
    def record_locator_failure(self, step_id: int) -> None:
        """
        记录定位失败
        
        Args:
            step_id: 测试步骤ID
        """
        locator = self.get_locator(step_id)
        if locator:
            locator.record_failure()
            self.db.commit()
            logger.debug(f"步骤 {step_id}: 记录定位失败")
    
    def update_locator(
        self,
        step_id: int,
        css_selector: Optional[str] = None,
        xpath: Optional[str] = None,
        element_id: Optional[str] = None
    ) -> bool:
        """
        更新元素定位信息
        
        Args:
            step_id: 测试步骤ID
            css_selector: CSS选择器
            xpath: XPath
            element_id: 元素ID
            
        Returns:
            是否更新成功
        """
        locator = self.get_locator(step_id)
        if not locator:
            return False
        
        if css_selector:
            locator.css_selector = css_selector
        if xpath:
            locator.xpath = xpath
        if element_id:
            locator.element_id = element_id
        
        locator.updated_at = utcnow()
        self.db.commit()
        
        logger.info(f"步骤 {step_id}: 元素定位信息已更新")
        return True
    
    def delete_locator(self, step_id: int) -> bool:
        """
        删除元素定位信息
        
        Args:
            step_id: 测试步骤ID
            
        Returns:
            是否删除成功
        """
        locator = self.get_locator(step_id)
        if not locator:
            return False
        
        self.db.delete(locator)
        self.db.commit()
        
        logger.info(f"步骤 {step_id}: 元素定位信息已删除")
        return True
    
    def get_locator_stats(self, step_id: int) -> Optional[Dict[str, Any]]:
        """
        获取定位统计信息
        
        Args:
            step_id: 测试步骤ID
            
        Returns:
            统计信息
        """
        locator = self.get_locator(step_id)
        if not locator:
            return None
        
        return {
            "step_id": step_id,
            "success_count": locator.success_count,
            "fail_count": locator.fail_count,
            "success_rate": locator.success_rate,
            "last_used_at": locator.last_used_at,
            "priority_order": locator.priority_order
        }
