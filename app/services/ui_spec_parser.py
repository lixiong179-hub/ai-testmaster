"""
UI Spec Parser Service - 摹客UI原型视觉解析服务
将摹客导出的UI图通过VLM解析为结构化JSON（ui_spec）
"""
import base64
import json
import time
import asyncio
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from app.utils.unified_vision_model import UnifiedVisionModel, get_default_vision_model, VisionModelType
from app.utils.ocr_extractor import OCRExtractor, OCRExtractorError
from app.core.config import settings
import requests


class UISpecParser:
    """
    UI原型图视觉解析服务

    将摹客导出的UI图通过VLM解析为结构化JSON（ui_spec）
    包括：页面元素、导航关系、布局约束、跳转流程等
    """

    # 解析单张UI图的提示词（视觉模式，包含视觉细节）
    SINGLE_IMAGE_PROMPT = """你是一个专业的UI/UX分析师。请仔细分析这张UI截图，并严格按照以下JSON格式输出结构化数据。

重要要求：
1. 只输出纯JSON，不要用```json...```包裹，不要输出任何解释性文字。
2. 字符串值如无内容请用""，数组为空请用[]，无法确定的字段用null。
3. 对于无法确定或存在歧义的内容，请在warnings数组中说明原因。
4. 充分利用你的视觉能力：描述颜色、图标、字体大小相对关系、间距、对齐方式等。

输出格式：
{
  "screen_name": "从页面内容推断的页面名称",
  "purpose": "页面的主要功能和目的",
  "regions": {
    "header": {"exists": true, "height_approx": "low|medium|high", "content": "顶部区域内容描述，包括颜色、背景等"},
    "content": {"scrollable": true/false, "layout_type": "list|grid|form|mixed", "description": "内容区域描述，包括背景色、间距等"},
    "footer": {"exists": false, "content": ""},
    "overlay": {"exists": false, "type": "dialog|drawer|popup", "description": ""}
  },
  "elements": [
    {
      "type": "button|input|text|icon|navigation|list_item|checkbox|radio|switch|slider|form|dropdown|image|video",
      "label": "可见的标签文字",
      "semantic": "语义化描述，如：提交按钮、用户名输入框",
      "position": "top_left|top_center|top_right|center|bottom_left|bottom_center|bottom_right|full_width",
      "state": "normal|disabled|selected|active|error|hidden",
      "interactive": true/false,
      "color": "前景色或背景色描述，如 '蓝色文字'、'白色背景'",
      "font_size": "small|medium|large 或相对描述（如 '比正文大'）",
      "icon": "图标描述（如 '左箭头'、'搜索图标'），无图标则为 null",
      "description": "详细描述，包括形状、边框、圆角、阴影等"
    }
  ],
  "navigation": {
    "back_button": {"visible": true/false, "position": "top_left|...", "label": "返回|←|... "},
    "tab_bar": {"visible": true/false, "items": ["首页", "我的"], "active_index": 0},
    "swipe_enabled": true/false,
    "nested_navigation": "其他导航元素描述或null"
  },
  "layout_constraints": [
    {
      "type": "alignment/spacing/sizing/color_contrast/fixed_position/overlay/safe_area",
      "description": "布局约束的具体描述，例如 '登录按钮水平居中，与输入框间距16dp'",
      "priority": "high/medium/low",
      "check_point": "可验证的检查点描述"
    }
  ],
  "flows": {
    "expected_next_screens": ["根据UI内容推断的可能跳转页面名称"],
    "trigger_actions": ["触发跳转的动作，如：点击提交按钮、选择列表项"]
  },
  "ui_adaptation_checks": [
    {
      "check_type": "element_visibility/text_overflow/layout_break/icon_size/button_tap_area/color_blind",
      "description": "UI适配检查项描述",
      "severity": "critical/major/minor"
    }
  ],
  "visual_style": {
    "background_color": "页面主背景色",
    "primary_color": "主题色（如按钮、链接颜色）",
    "border_radius": "全局圆角风格（无/小/中/大）",
    "shadow_usage": "是否有阴影效果"
  },
  "warnings": ["任何不确定或需要人工确认的内容"]
}

示例输出（仅供参考，请勿照抄）：
{
  "screen_name": "登录页",
  "purpose": "用户输入账号密码进行登录",
  "regions": {
    "header": {"exists": true, "height_approx": "low", "content": "白色背景，左侧返回箭头，中间标题'登录'"},
    "content": {"scrollable": false, "layout_type": "form", "description": "浅灰色背景，包含手机号输入框、密码输入框、登录按钮"},
    "footer": {"exists": false, "content": ""},
    "overlay": {"exists": false}
  },
  "elements": [
    {
      "type": "icon",
      "label": "",
      "semantic": "返回按钮",
      "position": "top_left",
      "state": "normal",
      "interactive": true,
      "color": "灰色",
      "font_size": null,
      "icon": "左箭头",
      "description": "左上角箭头图标，点击返回上一页"
    },
    {
      "type": "input",
      "label": "手机号",
      "semantic": "手机号输入框",
      "position": "center",
      "state": "normal",
      "interactive": true,
      "color": "#333333 文字",
      "font_size": "medium",
      "icon": "手机图标",
      "description": "带手机图标，占位文本'请输入手机号'，底部有灰色分割线"
    },
    {
      "type": "button",
      "label": "登录",
      "semantic": "登录提交按钮",
      "position": "center",
      "state": "normal",
      "interactive": true,
      "color": "白色文字，蓝色背景 #1890ff",
      "font_size": "large",
      "icon": null,
      "description": "圆角按钮，全宽，内边距12px"
    }
  ],
  "navigation": {
    "back_button": {"visible": true, "position": "top_left", "label": "←"},
    "tab_bar": {"visible": false},
    "swipe_enabled": false,
    "nested_navigation": null
  },
  "layout_constraints": [
    {
      "type": "alignment",
      "description": "所有表单控件水平居中，宽度为屏幕宽度的90%",
      "priority": "high",
      "check_point": "输入框和按钮水平居中对齐"
    },
    {
      "type": "spacing",
      "description": "输入框之间间距16px，按钮与上一个输入框间距24px",
      "priority": "medium",
      "check_point": "垂直间距符合设计规范"
    }
  ],
  "flows": {
    "expected_next_screens": ["首页", "注册页"],
    "trigger_actions": ["点击登录按钮", "点击注册链接"]
  },
  "ui_adaptation_checks": [
    {
      "check_type": "element_visibility",
      "description": "在窄屏幕（宽度<320px）下，输入框和按钮不应被截断",
      "severity": "major"
    },
    {
      "check_type": "color_contrast",
      "description": "蓝色按钮上的白色文字对比度足够",
      "severity": "minor"
    }
  ],
  "visual_style": {
    "background_color": "#F5F5F5",
    "primary_color": "#1890ff",
    "border_radius": "中等圆角（8px）",
    "shadow_usage": "按钮无阴影，卡片有轻微阴影"
  },
  "warnings": []
}

请开始分析这张UI截图："""

    # 多图合并生成页面流转的提示词（增强版）
    MULTI_IMAGE_FLOW_PROMPT = """你是一个专业的业务流程分析师。请根据以下UI截图序列，分析页面之间的流转关系。

截图序列（共{count}张）：

{image_descriptions}

请严格输出JSON格式：
{
  "entry_screen": "入口页面名称",
  "end_screens": ["可能的结束页面列表"],
  "page_flows": [
    {
      "from_screen": "来源页面",
      "to_screen": "目标页面",
      "trigger_action": "触发动作",
      "condition": "触发条件（如有）"
    }
  ],
  "navigation_map": {
    "页面A": {"can_go_to": ["页面B", "页面C"], "back_to": ["页面D"]}
  },
  "key_user_paths": [
    {"path_name": "主要用户路径", "steps": ["页面1", "页面2", "页面3"]}
  ],
  "warnings": ["任何不确定或缺失的流转信息"]
}

请开始分析："""

    # 批量解析的提示词（结合布局约束生成具体测试点）
    BATCH_SUMMARY_PROMPT = """你是一个测试用例生成专家。请根据以下已解析的UI屏幕规格，生成针对UI适配问题的专项测试用例检查点。

UI屏幕规格列表：
{ui_specs}

要求：
1. 每个屏幕的 ui_adaptation_test_points 应基于其 layout_constraints 生成具体的检查点。
2. 如果 layout_constraints 中存在 alignment、spacing、sizing 等约束，必须转化为对应的适配测试点。
3. 输出格式严格如下：

[
  {
    "screen_id": "屏幕ID",
    "ui_adaptation_test_points": [
      {
        "check_type": "layout/element_visibility/text_overflow/color_contrast/responsive_design/safe_area",
        "description": "检查项描述",
        "test_method": "测试方法（如：改变窗口宽度、使用大字体）",
        "expected_result": "预期结果",
        "severity": "critical/major/minor"
      }
    ]
  }
]

请开始补充："""

    # 文本结构化提示词（增强版，利用 OCR 位置顺序）
    TEXT_STRUCTURE_PROMPT = """你是一个专业的UI/UX分析师。以下是从UI截图中通过OCR提取的文字内容，每行前面的`[位置:数值]`表示该文本在垂直方向上的相对坐标（数值越小越靠近屏幕顶部）。请根据这些文字和位置信息，推断页面结构和元素，严格按照以下JSON格式输出。

{{
  "screen_name": "从页面内容推断的页面名称",
  "purpose": "页面的主要功能和目的",
  "elements": [
    {{
      "type": "button|input|text|link|dropdown|checkbox|switch|icon",
      "label": "可见的标签文字",
      "semantic": "语义化描述，如：提交按钮、用户名输入框",
      "position": "top|center|bottom（根据位置数值判断）",
      "interactive": true/false
    }}
  ],
  "navigation": {{
    "back_button": "返回按钮文字（如有）",
    "tab_bar": "Tab栏内容（如有）",
    "swipe_enabled": true/false
  }},
  "flows": {{
    "expected_next_screens": ["根据文字内容推断的可能跳转页面"],
    "trigger_actions": ["触发跳转的动作"]
  }},
  "warnings": ["任何无法确定或缺失的信息"]
}}

注意事项：
1. 如果文字内容无法确定类型，type 使用 "text"。
2. 根据常见的 UI 模式推断：例如“登录”、“注册”通常是按钮，“用户名”、“密码”通常是输入框标签。
3. 位置字段根据提供的数值粗略判断：top（前20%）、center（20%-80%）、bottom（80%以后）。
4. 仅输出纯JSON，不要输出解释。

以下是OCR提取的文字（带位置标记）：

{ocr_text}

请开始分析："""

    def __init__(self, vision_model: Optional[UnifiedVisionModel] = None, parse_mode: Optional[str] = None):
        self.vision_model = vision_model or get_default_vision_model()
        self.parse_mode = parse_mode or getattr(settings, 'UI_PARSER_MODE', 'text')
        self.max_retries = 3
        self.retry_delay = 2
        self._ocr_extractor: Optional[OCRExtractor] = None

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
            from app.core.config import settings
            resolved = Path(image_path).resolve()

            allowed_dirs = [
                Path(settings.UPLOAD_DIR).resolve(),
                Path(getattr(settings, 'UI_PROTOTYPE_UPLOAD_DIR', '/tmp/ui_prototypes')).resolve(),
                Path('/tmp/ui_prototypes').resolve(),
            ]

            is_allowed = any(str(resolved).startswith(str(allowed_dir)) for allowed_dir in allowed_dirs)

            if not is_allowed:
                logger.error(f"路径遍历攻击拦截: {image_path}")
                logger.error(f"  解析后路径: {resolved}")
                logger.error(f"  允许的目录: {[str(d) for d in allowed_dirs]}")
                return None
            if not resolved.is_file():
                logger.error(f"文件不存在: {image_path}")
                return None
            with open(resolved, "rb") as image_file:
                return image_file.read()
        except Exception as e:
            logger.error(f"图片读取失败: {image_path}, {str(e)}")
            return None

    def _get_ocr_extractor(self) -> OCRExtractor:
        """获取OCR提取器实例（懒加载）"""
        if self._ocr_extractor is None:
            self._ocr_extractor = OCRExtractor()
        return self._ocr_extractor

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

        如果 OCRExtractor 支持 extract_text_with_bbox 方法，则返回格式化的位置文本；
        否则返回 None，调用方应降级到纯文本。

        Returns:
            格式化的文本，如 "[位置:120] 登录按钮"；失败返回 None
        """
        try:
            extractor = self._get_ocr_extractor()
            # 尝试调用可能存在的带坐标方法
            if hasattr(extractor, 'extract_text_with_bbox'):
                blocks = extractor.extract_text_with_bbox(image_bytes)
                if blocks:
                    lines = []
                    for block in blocks:
                        # 假设每个 block 包含 text 和 bbox (ymin, ymax 或 y_center)
                        text = block.get('text', '')
                        # 获取垂直中心坐标
                        bbox = block.get('bbox', [0,0,0,0])
                        if len(bbox) >= 4:
                            y_center = (bbox[1] + bbox[3]) / 2
                        else:
                            y_center = block.get('y_center', 0)
                        lines.append(f"[位置:{int(y_center)}] {text}")
                    return "\n".join(lines)
            # 如果不支持，返回 None
            return None
        except Exception as e:
            logger.warning(f"提取位置信息失败: {e}")
            return None

    def _structure_text_with_llm(self, ocr_text: str, screen_name_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        使用LLM将OCR提取的文字结构化为UI规格（纯文本版）

        Args:
            ocr_text: OCR提取的文字内容
            screen_name_hint: 屏幕名称提示

        Returns:
            结构化的UI规格字典，失败返回None
        """
        prompt = self.TEXT_STRUCTURE_PROMPT.format(ocr_text=ocr_text)
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

    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """解析JSON响应，处理可能的不完整或带markdown格式的情况"""
        # 直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'\{\s*"screen_name"[\s\S]*\}',
            r'\{\s*"entry_screen"[\s\S]*\}',
            r'\{\s*"purpose"[\s\S]*\}',
            r'\[\s*\{[\s\S]*\}\s*\]',  # 数组格式（用于批量测试点）
        ]
        for pattern in json_patterns:
            match = re.search(pattern, content)
            if match:
                json_str = match.group(1) if '```' in pattern else match.group(0)
                try:
                    # 尝试修复常见问题：末尾多余逗号
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
        image_bytes = self._read_image_bytes(image_path)
        if not image_bytes:
            return False, {}, "图片读取失败"

        if self.parse_mode == "text":
            return await self._parse_with_text_mode(image_bytes, screen_name_hint)
        else:
            return await self._parse_with_vision_mode(image_bytes, screen_name_hint)

    async def _parse_with_text_mode(
        self,
        image_bytes: bytes,
        screen_name_hint: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        text模式解析：OCR提取文字（优先带位置） + LLM结构化

        Args:
            image_bytes: 图片字节数据
            screen_name_hint: 屏幕名称提示

        Returns:
            (成功标志, ui_spec字典, 错误信息)
        """
        # 尝试提取带位置信息的文本
        positioned_text = await asyncio.to_thread(self._extract_positioned_text, image_bytes)
        if positioned_text:
            ocr_text = positioned_text
            logger.info("使用带位置信息的OCR文本")
        else:
            # 降级到纯文本
            ocr_text = await asyncio.to_thread(self._extract_text_with_ocr, image_bytes)
            if not ocr_text:
                return False, {}, "OCR提取文字为空"
            logger.info("使用纯文本OCR（无位置信息）")

        result = await asyncio.to_thread(self._structure_text_with_llm, ocr_text, screen_name_hint)
        if result:
            return True, result, ""
        return False, {}, "文本结构化解析失败"

    async def _parse_with_vision_mode(
        self,
        image_bytes: bytes,
        screen_name_hint: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        vision模式解析：视觉模型直接分析图片

        Args:
            image_bytes: 图片字节数据
            screen_name_hint: 屏幕名称提示

        Returns:
            (成功标志, ui_spec字典, 错误信息)
        """
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
                    # 确保必要的字段存在
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

    async def parse_multiple_screen_flows(
        self,
        screens_data: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        多图合并生成页面流转（增强版：传入可点击元素）

        Args:
            screens_data: 屏幕数据列表，每项需包含 screen_id, screen_name, summary, elements 等

        Returns:
            页面流转图JSON
        """
        if len(screens_data) < 2:
            return None

        count = len(screens_data)
        image_descriptions = []

        for i, screen in enumerate(screens_data):
            desc = f"【屏幕{i+1}】{screen.get('screen_name', '未知')}\n"
            if screen.get('purpose'):
                desc += f"目的: {screen.get('purpose')}\n"
            # 提取可交互元素（按钮、链接、列表项）
            interactive_elements = []
            for elem in screen.get('elements', []):
                if elem.get('interactive') and elem.get('type') in ['button', 'link', 'list_item', 'icon']:
                    label = elem.get('label') or elem.get('semantic', '')
                    if label:
                        interactive_elements.append(label)
            if interactive_elements:
                desc += f"可点击元素: {', '.join(interactive_elements[:10])}\n"
            # 导航信息
            nav = screen.get('navigation', {})
            if nav.get('back_button', {}).get('visible'):
                desc += "存在返回按钮\n"
            if nav.get('tab_bar', {}).get('visible'):
                desc += f"Tab栏: {', '.join(nav['tab_bar'].get('items', []))}\n"
            # 预期跳转
            flows = screen.get('flows', {})
            if flows.get('expected_next_screens'):
                desc += f"预期跳转: {', '.join(flows['expected_next_screens'])}\n"
            if flows.get('trigger_actions'):
                desc += f"触发动作: {', '.join(flows['trigger_actions'])}\n"

            image_descriptions.append(desc)

        prompt = self.MULTI_IMAGE_FLOW_PROMPT.format(
            count=count,
            image_descriptions="\n\n".join(image_descriptions)
        )

        for attempt in range(self.max_retries):
            try:
                logger.info(f"生成页面流转，模式: {self.parse_mode}，尝试 {attempt + 1}/{self.max_retries}")

                response = await asyncio.to_thread(self.vision_model.analyze_text, prompt)
                result = self._parse_json_response(response)

                if result:
                    logger.info("页面流转生成成功")
                    return result

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

            except Exception as e:
                logger.error(f"页面流转生成异常: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

        return None

    async def generate_ui_adaptation_test_points(
        self,
        screens_data: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        为已解析的UI屏幕生成UI适配测试检查点（基于layout_constraints）

        Args:
            screens_data: 已解析的ui_spec列表，每项需包含 screen_id

        Returns:
            补充了测试检查点的屏幕数据列表
        """
        if not screens_data:
            return None

        # 为每个屏幕提取必要信息：screen_id, layout_constraints
        simplified = []
        for screen in screens_data:
            simplified.append({
                "screen_id": screen.get("screen_id", "unknown"),
                "screen_name": screen.get("screen_name", ""),
                "layout_constraints": screen.get("layout_constraints", [])
            })

        prompt = self.BATCH_SUMMARY_PROMPT.format(
            ui_specs=json.dumps(simplified, ensure_ascii=False, indent=2)
        )

        for attempt in range(self.max_retries):
            try:
                logger.info(f"生成UI适配测试点，尝试 {attempt + 1}/{self.max_retries}")

                response = await asyncio.to_thread(self.vision_model.analyze_text, prompt)
                result = self._parse_json_response(response)

                if result and isinstance(result, list):
                    logger.info("UI适配测试点生成成功")
                    return result

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

            except Exception as e:
                logger.error(f"UI适配测试点生成异常: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

        return None


# 全局实例
ui_spec_parser = UISpecParser()


async def parse_ui_screen_async(image_path: str, screen_name_hint: Optional[str] = None) -> Tuple[bool, Dict[str, Any], str]:
    """异步解析单张UI图"""
    return await ui_spec_parser.parse_single_screen(image_path, screen_name_hint)


async def parse_ui_flow_sync(screens_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """异步生成页面流转"""
    return await ui_spec_parser.parse_multiple_screen_flows(screens_data)
