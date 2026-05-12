"""UI解析核心Mixin - 提供单页面解析和JSON校验能力。
"""
import json
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from loguru import logger
from app.core.config import settings


class UISpecCoreMixin:
    def _read_image_bytes(self, image_path: str) -> Optional[bytes]:
        try:
            resolved = Path(image_path).resolve()
            allowed_dirs = [
                Path(settings.UPLOAD_DIR).resolve(),
                Path(settings.UI_PROTOTYPE_UPLOAD_DIR).resolve(),
            ]
            is_allowed = any(resolved.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs)
            if not is_allowed:
                logger.error(f"路径遍历攻击拦截: {image_path}")
                return None
            if not resolved.is_file():
                logger.error(f"文件不存在: {image_path}")
                return None
            with open(resolved, "rb") as image_file:
                return image_file.read()
        except Exception as e:
            logger.error(f"图片读取失败: {image_path}, {str(e)}")
            return None

    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'\{\s*"screen_name"[\s\S]*\}',
            r'\{\s*"entry_screen"[\s\S]*\}',
            r'\{\s*"purpose"[\s\S]*\}',
            r'\[\s*\{[\s\S]*\}\s*\]',
        ]
        for pattern in json_patterns:
            match = re.search(pattern, content)
            if match:
                json_str = match.group(1) if '```' in pattern else match.group(0)
                try:
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        logger.warning(f"无法解析JSON响应: {content[:200]}...")
        return None

    async def parse_single_screen(
        self,
        image_path: str,
        screen_name_hint: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        image_bytes = self._read_image_bytes(image_path)
        if not image_bytes:
            return False, {}, "图片读取失败"
        if self.parse_mode == settings.PARSE_MODE_TEXT:
            return await self._parse_with_text_mode(image_bytes, screen_name_hint)
        return await self._parse_with_vision_mode(image_bytes, screen_name_hint)

    async def _parse_with_text_mode(
        self,
        image_bytes: bytes,
        screen_name_hint: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        positioned_text = await asyncio.to_thread(self._ocr_helper.extract_positioned_text, image_bytes)
        if positioned_text:
            ocr_text = positioned_text
            logger.info("使用带位置信息的OCR文本")
        else:
            ocr_text = await asyncio.to_thread(self._ocr_helper.extract_text, image_bytes)
            if not ocr_text:
                return False, {}, "OCR提取文字为空"
            logger.info("使用纯文本OCR（无位置信息）")
        result = await asyncio.to_thread(self._ocr_helper.structure_text_with_llm, ocr_text, screen_name_hint)
        if result:
            return True, result, ""
        return False, {}, "文本结构化解析失败"

    async def _parse_with_vision_mode(
        self,
        image_bytes: bytes,
        screen_name_hint: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        prompt = self.SINGLE_IMAGE_PROMPT
        if screen_name_hint:
            prompt = f"[提示：这是{screen_name_hint}]\n\n" + prompt
        for attempt in range(self.max_retries):
            try:
                logger.info(f"视觉模型解析UI图，尝试 {attempt + 1}/{self.max_retries}")
                response = await asyncio.to_thread(
                    self.vision_model.analyze_image,
                    screenshot=image_bytes,
                    prompt=prompt
                )
                logger.info(f"视觉模型原始响应: {response[:500] if response else 'None'}")
                result = self._parse_json_response(response)
                if result:
                    if "warnings" not in result:
                        result["warnings"] = []
                    logger.info("视觉模型解析成功")
                    return True, result, ""
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
            except Exception as e:
                logger.error(f"视觉模型解析异常: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                return False, {}, f"解析异常: {e}"
        return False, {}, "解析失败，已达最大重试次数"
