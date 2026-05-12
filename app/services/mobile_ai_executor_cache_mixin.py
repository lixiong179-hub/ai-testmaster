"""移动端AI缓存Mixin - 缓存AI识别结果避免重复识别。
"""
import json
import asyncio
from typing import Optional, Dict, Any
from loguru import logger
from app.models.element_locator import ElementLocator
from app.services.mobile_ai_executor_types import MobileRecognitionError


class MobileAICacheMixin:
    async def _find_element(self, element_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cache_key = self._generate_cache_key(element_info)
        cached = self._get_cached_locator(cache_key)
        if cached:
            try:
                if cached.get('resource_id'):
                    elements = self.uiautomator_helper.find_elements(resource_id=cached['resource_id'])
                    if elements:
                        return cached
                elif cached.get('text'):
                    elements = self.uiautomator_helper.find_elements(text=cached['text'])
                    if elements:
                        return cached
            except Exception:
                pass
        locator = await self._ai_recognize_element(element_info)
        if locator:
            self._cache_locator(cache_key, locator)
        return locator

    async def _ai_recognize_element(self, element_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            screenshot = self.adb_controller.screenshot()
            if not screenshot:
                raise MobileRecognitionError("截图失败")
            description = element_info.get('description', '')
            element_type = element_info.get('type', '')
            prompt = f"请在截图中找到以下UI元素并返回其位置信息：\n描述：{description}\n类型：{element_type}\n请返回JSON格式：{{\"x\": 数字, \"y\": 数字, \"confidence\": 0-1, \"resource_id\": \"可选\", \"text\": \"可选\"}}"
            response = await asyncio.to_thread(
                self.vision_model.analyze_image,
                screenshot=screenshot,
                prompt=prompt
            )
            if not response:
                raise MobileRecognitionError("AI识别返回为空")
            result = self._parse_ai_response(response)
            if result and result.get('confidence', 0) >= self.confidence_threshold:
                locator = {}
                if result.get('x') and result.get('y'):
                    locator['coordinates'] = {'x': result['x'], 'y': result['y']}
                if result.get('resource_id'):
                    locator['resource_id'] = result['resource_id']
                if result.get('text'):
                    locator['text'] = result['text']
                locator['confidence'] = result['confidence']
                return locator
            logger.warning(f"AI识别置信度不足: {result.get('confidence', 0) if result else 0}")
            return None
        except MobileRecognitionError:
            raise
        except Exception as e:
            logger.error(f"AI识别异常: {e}")
            raise MobileRecognitionError(f"AI识别异常: {e}")

    def _generate_cache_key(self, element_info: Dict[str, Any]) -> str:
        parts = [
            element_info.get('description', ''),
            element_info.get('type', ''),
            str(element_info.get('resource_id', '')),
            str(element_info.get('text', ''))
        ]
        return '|'.join(parts)

    def _get_cached_locator(self, cache_key: str) -> Optional[Dict[str, Any]]:
        if not self.db:
            return None
        try:
            locator = self.db.query(ElementLocator).filter(
                ElementLocator.cache_key == cache_key,
                ElementLocator.is_active == True
            ).first()
            if locator:
                result = {'confidence': locator.confidence or 0.0}
                if locator.css_selector:
                    result['resource_id'] = locator.css_selector
                if locator.xpath:
                    result['xpath'] = locator.xpath
                if locator.text_match:
                    result['text'] = locator.text_match
                return result
        except Exception as e:
            logger.warning(f"缓存查询失败: {e}")
        return None

    def _cache_locator(self, cache_key: str, locator: Dict[str, Any]) -> None:
        if not self.db:
            return
        try:
            existing = self.db.query(ElementLocator).filter(
                ElementLocator.cache_key == cache_key
            ).first()
            if existing:
                existing.confidence = locator.get('confidence', 0.0)
                if locator.get('resource_id'):
                    existing.css_selector = locator['resource_id']
                if locator.get('xpath'):
                    existing.xpath = locator['xpath']
                if locator.get('text'):
                    existing.text_match = locator['text']
                existing.is_active = True
            else:
                new_locator = ElementLocator(
                    cache_key=cache_key,
                    confidence=locator.get('confidence', 0.0),
                    css_selector=locator.get('resource_id'),
                    xpath=locator.get('xpath'),
                    text_match=locator.get('text'),
                    is_active=True
                )
                self.db.add(new_locator)
            self.db.commit()
        except Exception as e:
            logger.warning(f"缓存存储失败: {e}")
            if self.db:
                self.db.rollback()

    def _parse_ai_response(self, response: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        return None
