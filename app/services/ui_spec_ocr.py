"""UI规格OCR模块 - 从UI原型图中提取文字并结构化为UI规格。

本模块提供OCR文字提取和LLM结构化能力，用于text解析模式下
从UI原型图中提取文字内容，再通过LLM将纯文本结构化为标准
UI规格格式。

核心类:
    - UISpecOCR: OCR文字提取与LLM结构化工具

依赖关系:
    - app.utils.ocr_extractor: OCR文字提取引擎
    - app.services.prompt_builder: TEXT_STRUCTURE_PROMPT模板

解析流程:
    1. 使用OCR引擎提取图片中的文字（纯文本或带位置信息）
    2. 将OCR文本通过LLM结构化为UI规格JSON

容错设计:
    - OCR提取失败返回空字符串，不抛出异常
    - LLM结构化支持重试机制（最多3次）
    - JSON解析支持多种格式（纯JSON/Markdown代码块/混合文本）
"""
import time
from typing import Dict, Any, Optional
from loguru import logger
from app.utils.ocr_extractor import OCRExtractor, OCRExtractorError
from app.services.prompt_builder import TEXT_STRUCTURE_PROMPT


class UISpecOCR:
    """OCR文字提取与LLM结构化工具。

    职责:
        - 从图片中提取纯文本内容
        - 从图片中提取带位置信息的文本（垂直坐标）
        - 将OCR文本通过LLM结构化为UI规格JSON
        - 解析LLM返回的JSON响应（兼容多种格式）

    使用场景:
        - text解析模式下替代视觉模型直接分析
        - 文字密集型UI的规格提取
        - 需要精确文字内容的场景

    重试策略:
        LLM结构化调用最多重试3次，每次间隔retry_delay秒。
        OCR提取不重试（底层引擎已有容错机制）。
    """

    def __init__(self, vision_model: Any, ocr_extractor: Optional[OCRExtractor] = None, max_retries: int = 3, retry_delay: int = 2) -> None:
        """初始化OCR工具。

        Args:
            vision_model: 视觉模型实例，用于LLM结构化调用。
            ocr_extractor: OCR提取器实例，可选，延迟创建。
            max_retries: LLM调用最大重试次数，默认3。
            retry_delay: 重试间隔秒数，默认2。
        """
        self.vision_model = vision_model
        self._ocr_extractor = ocr_extractor
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _get_ocr_extractor(self) -> OCRExtractor:
        """获取OCR提取器实例，采用延迟加载模式。

        Returns:
            OCRExtractor实例。
        """
        if self._ocr_extractor is None:
            self._ocr_extractor = OCRExtractor()
        return self._ocr_extractor

    def extract_text(self, image_bytes: bytes) -> str:
        """使用OCR从图片中提取纯文本内容（不含位置信息）。

        Args:
            image_bytes: 图片字节数据。

        Returns:
            提取的文字内容，提取失败返回空字符串。
        """
        try:
            extractor = self._get_ocr_extractor()
            text = extractor.extract_text(image_bytes)
            if not text or not text.strip():
                logger.warning("OCR提取的文字为空")
                return ""
            logger.info(f"OCR提取文字成功，共{len(text)}字符")
            return text
        except OCRExtractorError as e:
            logger.error(f"OCR提取失败: {e}")
            return ""
        except Exception as e:
            logger.error(f"OCR提取异常: {e}")
            return ""

    def extract_positioned_text(self, image_bytes: bytes) -> Optional[str]:
        """尝试提取带位置信息的文字（垂直坐标）。

        输出格式: "[位置:120] 登录按钮"，位置为元素中心的Y坐标。
        用于需要按垂直顺序排列UI元素的场景。

        Args:
            image_bytes: 图片字节数据。

        Returns:
            格式化的带位置文本，提取失败返回None。
        """
        try:
            extractor = self._get_ocr_extractor()
            if hasattr(extractor, 'extract_text_with_bbox'):
                blocks = extractor.extract_text_with_bbox(image_bytes)
                if blocks:
                    lines = []
                    for block in blocks:
                        text = block.get('text', '')
                        bbox = block.get('bbox', [0, 0, 0, 0])
                        if len(bbox) >= 4:
                            # 计算元素中心的Y坐标
                            y_center = (bbox[1] + bbox[3]) / 2
                        else:
                            y_center = block.get('y_center', 0)
                        lines.append(f"[位置:{int(y_center)}] {text}")
                    return "\n".join(lines)
            return None
        except Exception as e:
            logger.warning(f"提取位置信息失败: {e}")
            return None

    def structure_text_with_llm(self, ocr_text: str, screen_name_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """使用LLM将OCR提取的文字结构化为UI规格（纯文本版）。

        将OCR文本填入TEXT_STRUCTURE_PROMPT模板，调用LLM生成
        结构化的UI规格JSON。支持重试机制。

        Args:
            ocr_text: OCR提取的文字内容。
            screen_name_hint: 屏幕名称提示，可选。

        Returns:
            结构化的UI规格字典，失败返回None。
        """
        prompt = TEXT_STRUCTURE_PROMPT.replace('{ocr_text}', ocr_text)
        if screen_name_hint:
            prompt = f"[提示：这是{screen_name_hint}]\n\n" + prompt

        for attempt in range(self.max_retries):
            try:
                logger.info(f"文本结构化解析，尝试 {attempt + 1}/{self.max_retries}")
                response = self.vision_model.analyze_text(prompt)
                result = self._parse_json_response(response)
                if result:
                    logger.info("文本结构化解析成功")
                    return result
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
            except Exception as e:
                logger.error(f"文本结构化解析异常: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
        return None

    @staticmethod
    def _parse_json_response(content: str) -> Optional[Dict[str, Any]]:
        """解析LLM返回的JSON响应，兼容多种格式。

        支持的格式:
            1. 纯JSON字符串
            2. Markdown代码块包裹的JSON（```json ... ```）
            3. 混合文本中嵌入的JSON对象
            4. 尾部逗号的JSON（自动修复）

        Args:
            content: LLM返回的原始文本。

        Returns:
            解析后的字典，解析失败返回None。
        """
        import json
        import re

        # 优先尝试直接JSON解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 按优先级尝试多种JSON提取模式
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # Markdown json代码块
            r'```\s*([\s\S]*?)\s*```',        # Markdown 代码块
            r'\{\s*"screen_name"[\s\S]*\}',   # 以screen_name开头的JSON
            r'\{\s*"entry_screen"[\s\S]*\}',  # 以entry_screen开头的JSON
            r'\{\s*"purpose"[\s\S]*\}',       # 以purpose开头的JSON
            r'\[\s*\{[\s\S]*\}\s*\]',         # JSON数组
        ]
        for pattern in json_patterns:
            match = re.search(pattern, content)
            if match:
                json_str = match.group(1) if '```' in pattern else match.group(0)
                try:
                    # 修复尾部逗号问题（LLM常见输出错误）
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue

        logger.warning(f"无法解析JSON响应: {content[:200]}...")
        return None
