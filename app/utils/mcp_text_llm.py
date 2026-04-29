"""
MCP文本LLM工具模块

提供基于视觉大模型的UI元素定位理解能力，将自然语言操作描述
转换为结构化的元素定位信息。是AI自动化测试中"理解用户意图"的核心组件。

工作流程：
    1. 接收Accessibility Tree快照和用户操作描述
    2. 构建定位理解Prompt，发送给视觉大模型
    3. 解析模型返回的JSON，提取定位方式和定位值
    4. 返回结构化定位结果（locator_type + locator_value + confidence）

定位方式优先级（从高到低）：
    1. role + text: 最稳定，如 button[登录]
    2. text: 通过可见文本定位
    3. css: 通过CSS选择器定位
    4. ref: 通过Accessibility Tree引用ID定位（兜底方案）

核心类：
    - MCPAwareLLM: MCP感知的LLM客户端

全局实例：
    - get_mcp_llm(): 获取全局MCPAwareLLM单例

依赖：
    - app.utils.unified_vision_model: 统一视觉模型（多模型适配）
    - app.core.config.settings: 全局配置
"""
import asyncio
import json
import re
from typing import Optional, Dict, Any

from loguru import logger

from app.utils.unified_vision_model import UnifiedVisionModel, get_default_vision_model
from app.core.config import settings


# 元素定位理解Prompt模板 — 指导AI分析Accessibility Tree并输出结构化定位信息
LOCATOR_UNDERSTANDING_PROMPT = """页面Accessibility Tree快照:
{accessibility_tree}

用户操作描述: {operation_description}

请根据Accessibility Tree快照，确定用户要操作的元素，并给出最佳定位方式。

返回JSON格式:
{
  "locator_type": "role|text|css|xpath|ref",
  "locator_value": "定位值",
  "element_description": "元素描述",
  "confidence": 0.0-1.0,
  "reasoning": "选择该定位方式的理由"
}

定位方式优先级:
1. role + text: 如 {"locator_type": "role", "locator_value": "button[登录]"} 表示role为button且文本为登录
2. text: 如 {"locator_type": "text", "locator_value": "提交"} 表示通过可见文本定位
3. css: 如 {"locator_type": "css", "locator_value": "#submit-btn"} 表示通过CSS选择器定位
4. ref: 如 {"locator_type": "ref", "locator_value": "abc123"} 表示通过Accessibility Tree中的ref引用定位

注意:
- 优先使用 role + text 方式，最稳定
- 如果元素有唯一文本，使用 text 方式
- 如果元素有id，使用 css 方式
- 如果以上都不适用，使用 ref 方式（从Accessibility Tree中获取的引用ID）
- 严格返回JSON，不要返回解释性文字
- 如果无法确定目标元素，返回 {"locator_type": "", "locator_value": "", "confidence": 0}"""


class MCPAwareLLM:
    """MCP感知的LLM客户端

    封装视觉大模型，提供UI元素定位理解能力。
    将Accessibility Tree快照和自然语言操作描述作为输入，
    输出结构化的元素定位信息。

    设计要点：
        - 延迟初始化视觉模型，首次使用时才创建实例
        - 支持批量操作理解，减少模型调用次数
        - 使用asyncio.to_thread将同步模型调用转为异步，不阻塞事件循环

    Attributes:
        _vision_model: 统一视觉模型实例（延迟初始化）
    """

    def __init__(self, vision_model: Optional[UnifiedVisionModel] = None):
        self._vision_model = vision_model

    @property
    def vision_model(self) -> UnifiedVisionModel:
        """获取视觉模型实例（延迟初始化）

        首次访问时通过get_default_vision_model()创建默认实例，
        后续访问直接返回已创建的实例。

        Returns:
            UnifiedVisionModel: 视觉模型实例
        """
        if self._vision_model is None:
            self._vision_model = get_default_vision_model()
        return self._vision_model

    async def understand_operation(
        self,
        accessibility_tree: str,
        operation_description: str,
        action_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """理解用户操作意图，返回元素定位信息

        将Accessibility Tree和操作描述发送给视觉大模型，
        解析返回的JSON获取定位方式和定位值。

        Args:
            accessibility_tree: 页面Accessibility Tree快照文本
            operation_description: 用户的自然语言操作描述
            action_type: 操作类型提示（如click/input），可选

        Returns:
            Optional[Dict[str, Any]]: 定位结果字典，包含：
                - locator_type: 定位方式（role/text/css/xpath/ref）
                - locator_value: 定位值
                - element_description: 元素描述
                - confidence: 置信度（0-1）
                - reasoning: 选择理由
                解析失败返回None
        """
        # 截断过长的Accessibility Tree，避免超出模型上下文窗口
        prompt = LOCATOR_UNDERSTANDING_PROMPT.replace('{accessibility_tree}', accessibility_tree[:8000]).replace('{operation_description}', operation_description)

        if action_type:
            prompt += f"\n\n操作类型提示: {action_type}"

        try:
            # 使用to_thread将同步调用转为异步，避免阻塞事件循环
            response = await asyncio.to_thread(self.vision_model.analyze_text, prompt)
            return self.parse_locator_result(response)
        except Exception as e:
            logger.error(f"LLM理解操作意图失败: {e}")
            return None

    async def batch_understand_operations(
        self,
        accessibility_tree: str,
        operations: list
    ) -> list:
        """批量理解操作意图

        对同一页面的多个操作描述逐个调用understand_operation，
        共享同一份Accessibility Tree快照以减少重复传输。

        Args:
            accessibility_tree: 页面Accessibility Tree快照文本
            operations: 操作描述列表，每项可以是字符串或字典：
                - 字符串: 操作描述文本
                - 字典: {"description": "...", "action_type": "..."}

        Returns:
            list: 定位结果列表，与输入operations一一对应，失败项为None
        """
        results = []
        for op in operations:
            if isinstance(op, str):
                desc = op
                action_type = None
            elif isinstance(op, dict):
                desc = op.get("description", "")
                action_type = op.get("action_type")
            else:
                results.append(None)
                continue
            result = await self.understand_operation(accessibility_tree, desc, action_type)
            results.append(result)
        return results

    @staticmethod
    def parse_locator_result(response: str) -> Optional[Dict[str, Any]]:
        """解析LLM返回的定位结果

        从模型返回的文本中提取JSON，验证必要字段是否存在。
        要求返回的JSON包含locator_type和locator_value字段，
        缺少任一字段视为定位失败。

        Args:
            response: LLM返回的原始文本

        Returns:
            Optional[Dict[str, Any]]: 解析成功的定位结果字典，失败返回None
        """
        if not response:
            return None
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return None
            result = json.loads(json_match.group())
            locator_type = result.get("locator_type", "")
            locator_value = result.get("locator_value", "")
            confidence = float(result.get("confidence", 0))
            if not locator_type or not locator_value:
                return None
            return {
                "locator_type": locator_type,
                "locator_value": locator_value,
                "element_description": result.get("element_description", ""),
                "confidence": confidence,
                "reasoning": result.get("reasoning", "")
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"解析LLM定位结果失败: {e}")
            return None


# 全局MCPAwareLLM单例 — 延迟初始化，首次调用get_mcp_llm()时创建
_mcp_llm: Optional[MCPAwareLLM] = None


def get_mcp_llm() -> MCPAwareLLM:
    """获取全局MCPAwareLLM单例

    首次调用时创建实例，后续调用返回同一实例。

    Returns:
        MCPAwareLLM: 全局MCPAwareLLM实例
    """
    global _mcp_llm
    if _mcp_llm is None:
        _mcp_llm = MCPAwareLLM()
    return _mcp_llm


__all__ = [
    'MCPAwareLLM',
    'LOCATOR_UNDERSTANDING_PROMPT',
    'get_mcp_llm',
]
