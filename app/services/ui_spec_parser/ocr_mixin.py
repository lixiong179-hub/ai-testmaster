"""
UI Spec Parser - OCR与文本模型Mixin
提供OCR文字提取、带位置信息提取、LLM文本结构化能力
"""
import time
from typing import Dict, Any, Optional
from loguru import logger

from app.utils.ocr_extractor import OCRExtractor, OCRExtractorError
from app.core.config import settings


class UISpecOcrMixin:
    """OCR与文本模型相关方法Mixin"""

    def _get_ocr_extractor(self) -> OCRExtractor:
        """获取OCR提取器实例（懒加载）"""
        if self._ocr_extractor is None:
            self._ocr_extractor = OCRExtractor()
        return self._ocr_extractor

    def _get_text_model(self) -> "OpenAI":
        """
        获取 DeepSeek 文本模型实例（懒加载）。
        用于 text 模式的 OCR 结果结构化，根据配置初始化模型客户端。
        首次调用时创建实例，后续直接返回缓存。
        """
        if self._text_model is None:
            from openai import OpenAI
            from app.utils.ai_client_core import get_ai_client
            text_api_key = getattr(settings, 'TEXT_MODEL_API_KEY', '') or settings.DEEPSEEK_API_KEY
            text_base_url = getattr(settings, 'TEXT_MODEL_API_URL', '') or getattr(settings, 'DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
            text_model_name = getattr(settings, 'TEXT_MODEL_NAME', '') or settings.DEEPSEEK_MODEL
            self._text_model = get_ai_client(
                api_key=text_api_key,
                base_url=text_base_url,
                model_name=text_model_name
            )
            logger.info(f"初始化文本模型: {text_model_name}, base_url: {text_base_url}")
        return self._text_model

    def _extract_text_with_ocr(self, image_bytes: bytes) -> str:
        """
        使用OCR从图片中提取文字（仅纯文本，不含位置）

        Args:
            image_bytes: 图片字节数据

        Returns:
            提取的文字内容，失败返回空字符串
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

    def _extract_positioned_text(self, image_bytes: bytes) -> Optional[str]:
        """
        尝试提取带位置信息的文字（垂直坐标）

        Returns:
            格式化的文本，如 "[位置:120] 登录按钮"；失败返回 None
        """
        logger.debug("[_extract_positioned_text] 开始")
        try:
            extractor = self._get_ocr_extractor()
            logger.debug(f"  已获取 OCR extractor: {extractor is not None}")
            blocks = extractor.extract_text_with_position(image_bytes)
            logger.debug(f"  extract_text_with_position 返回: {type(blocks)}, 长度: {len(blocks) if blocks else 0}")
            if blocks:
                lines = []
                for block in blocks:
                    text = block.get('text', '')
                    y_pos = block.get('y', 0)
                    lines.append(f"[位置:{y_pos}] {text}")
                result = "\n".join(lines)
                logger.debug(f"  返回结果: {result[:150]}")
                return result
            logger.warning("  blocks 为空")
            return None
        except Exception as e:
            logger.error(f"提取位置信息失败: {e}")
            import traceback
            logger.error(f"  堆栈: {traceback.format_exc()}")
            return None

    def _structure_text_with_llm(
        self,
        ocr_text: str,
        screen_name_hint: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        使用 DeepSeek 文本模型将 OCR 提取的文字结构化为 UI 规格。
        在 text 模式下调用，避免使用视觉模型以降低成本。

        Args:
            ocr_text: OCR 提取的文字内容
            screen_name_hint: 屏幕名称提示

        Returns:
            结构化的 UI 规格字典，失败返回 None
        """
        from app.services.ui_spec_prompts import TEXT_STRUCTURE_PROMPT
        prompt = TEXT_STRUCTURE_PROMPT.format(ocr_text=ocr_text)
        if screen_name_hint:
            prompt = f"[提示：这是{screen_name_hint}]\n\n" + prompt

        for attempt in range(self.max_retries):
            try:
                logger.info(f"文本结构化解析，使用 DeepSeek 模型，尝试 {attempt + 1}/{self.max_retries}")
                text_model = self._get_text_model()
                response = text_model.chat.completions.create(
                    model=text_model.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=2048,
                    timeout=60.0
                )
                result_text = response.choices[0].message.content
                result = self._parse_json_response(result_text)
                if result:
                    logger.info("文本结构化解析成功")
                    return result
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "authentication" in error_msg.lower():
                    logger.error("DeepSeek API 认证失败：API 密钥无效或已过期")
                elif "429" in error_msg or "rate limit" in error_msg.lower():
                    logger.warning("DeepSeek API 调用频率超限，触发限流保护")
                elif "timeout" in error_msg.lower():
                    logger.warning(f"DeepSeek API 调用超时（尝试 {attempt + 1}/{self.max_retries}）")
                elif "connection" in error_msg.lower():
                    logger.error(f"DeepSeek API 网络连接失败：{error_msg}")
                else:
                    logger.error(f"文本结构化解析异常：{error_msg}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        return None
