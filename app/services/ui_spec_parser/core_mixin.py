"""
UI Spec Parser - 核心解析Mixin
提供图片读取、JSON解析、单屏视觉/text模式解析能力
"""
import base64
import asyncio
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from loguru import logger

from app.core.config import settings


class UISpecCoreMixin:
    """核心解析方法Mixin"""

    def _encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """将图片文件编码为base64"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"图片编码失败: {image_path}, {str(e)}")
            return None

    def _read_image_bytes(self, image_path: str) -> Optional[bytes]:
        """读取图片文件字节数据（含路径遍历安全检查）"""
        try:
            logger.debug(f"[_read_image_bytes] 开始读取图片: {image_path}")
            resolved = Path(image_path).resolve()
            logger.debug(f"  解析后路径: {resolved}")

            # 白名单目录均来自配置项，跨平台兼容（Windows/Linux/macOS）
            # 使用 Path.resolve() 消除符号链接和 .. 穿越，再用 is_relative_to 校验前缀
            allowed_dirs = [
                Path(settings.UPLOAD_DIR).resolve(),
                Path(settings.UI_PROTOTYPE_UPLOAD_DIR).resolve(),
            ]
            logger.debug(f"  允许的目录: {[str(d) for d in allowed_dirs]}")

            # is_relative_to 在 resolve() 之后使用，可防御 ../../etc/passwd 等路径穿越
            is_allowed = any(resolved.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs)
            logger.debug(f"  路径是否允许: {is_allowed}")

            if not is_allowed:
                logger.error(f"路径遍历攻击拦截: {image_path}")
                return None
            if not resolved.is_file():
                logger.error(f"文件不存在: {image_path}")
                return None

            file_size = resolved.stat().st_size
            if file_size < 1024:
                logger.error(f"文件过小({file_size} bytes)，可能是损坏的图片: {image_path}")
                return None

            with open(resolved, "rb") as image_file:
                bytes_data = image_file.read()
                logger.debug(f"  读取成功，大小: {len(bytes_data)} bytes")

                import cv2
                import numpy as np
                nparr = np.frombuffer(bytes_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    logger.error(f"图片解码失败，文件可能已损坏: {image_path}")
                    return None

                if img.shape[0] < 10 or img.shape[1] < 10:
                    logger.error(f"图片尺寸过小({img.shape[1]}x{img.shape[0]})，无法进行OCR识别: {image_path}")
                    return None

                return bytes_data
        except Exception as e:
            logger.error(f"图片读取失败: {image_path}, {str(e)}")
            import traceback
            logger.error(f"  堆栈: {traceback.format_exc()}")
            return None

    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """解析JSON响应，处理可能的不完整或带markdown格式的情况"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.debug("直接JSON解析失败，尝试正则提取")

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
        """
        解析单张UI图（支持双模式）

        - text模式：OCR提取文字 + LLM结构化（优先使用带位置信息）
        - vision模式：视觉模型直接分析

        Args:
            image_path: 图片文件路径
            screen_name_hint: 屏幕名称提示

        Returns:
            (成功标志, ui_spec字典, 错误信息)
        """
        logger.info(f"[parse_single_screen] 开始解析，路径: {image_path}, 提示: {screen_name_hint}")
        logger.info(f"  解析模式: {self.parse_mode}")
        logger.info(f"  _ocr_extractor 是否已初始化: {self._ocr_extractor is not None}")

        image_bytes = self._read_image_bytes(image_path)
        logger.info(f"  _read_image_bytes 结果: {image_bytes is not None}")
        if not image_bytes:
            logger.error("  图片读取失败！")
            return False, {}, "图片读取失败"

        logger.info(f"  准备调用 _parse_with_{self.parse_mode}_mode")
        if self.parse_mode == settings.PARSE_MODE_TEXT:
            logger.info("  调用 _parse_with_text_mode")
            result = await self._parse_with_text_mode(image_bytes, screen_name_hint)
            logger.info(f"  _parse_with_text_mode 返回: {result}")
            return result
        else:
            logger.info("  调用 _parse_with_vision_mode")
            result = await self._parse_with_vision_mode(image_bytes, screen_name_hint)
            logger.info(f"  _parse_with_vision_mode 返回: {result}")
            return result

    async def _parse_with_text_mode(
        self,
        image_bytes: bytes,
        screen_name_hint: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        text模式解析：OCR提取文字（优先带位置） + LLM结构化

        Returns:
            (成功标志, ui_spec字典, 错误信息)
        """
        logger.debug(f"[_parse_with_text_mode] 开始解析，image_bytes 大小: {len(image_bytes) if image_bytes else 0}")
        logger.debug(f"  parse_mode: {self.parse_mode}")

        logger.debug("  开始调用 _extract_positioned_text")
        positioned_text = await asyncio.to_thread(self._extract_positioned_text, image_bytes)
        logger.debug(f"  _extract_positioned_text 结果: {positioned_text is not None}")
        if positioned_text:
            logger.debug(f"  positioned_text 长度: {len(positioned_text)}")
            logger.debug(f"  positioned_text 前100字符: {positioned_text[:100]}")
            ocr_text = positioned_text
            logger.info("使用带位置信息的OCR文本")
        else:
            logger.warning("  positioned_text 为空，降级到 _extract_text_with_ocr")
            ocr_text = await asyncio.to_thread(self._extract_text_with_ocr, image_bytes)
            logger.debug(f"  _extract_text_with_ocr 结果: {ocr_text is not None}")
            if ocr_text:
                logger.debug(f"  ocr_text 长度: {len(ocr_text)}")
            if not ocr_text:
                logger.error("  OCR提取文字为空！")
                return False, {}, "OCR提取文字为空"
            logger.info("使用纯文本OCR（无位置信息）")

        logger.debug("  开始调用 _structure_text_with_llm")
        result = await asyncio.to_thread(self._structure_text_with_llm, ocr_text, screen_name_hint)
        logger.debug(f"  _structure_text_with_llm 结果: {result is not None}")
        if result:
            return True, result, ""
        logger.error("  文本结构化解析失败！")
        return False, {}, "文本结构化解析失败"

    async def _parse_with_vision_mode(
        self,
        image_bytes: bytes,
        screen_name_hint: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        vision模式解析：视觉模型直接分析图片

        Returns:
            (成功标志, ui_spec字典, 错误信息)
        """
        from app.services.prompt_builder import SINGLE_IMAGE_PROMPT
        prompt = SINGLE_IMAGE_PROMPT
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
