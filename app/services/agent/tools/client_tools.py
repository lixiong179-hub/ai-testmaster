"""客户端工具集 - 通过 execution_callback 回调测试执行引擎执行。

6 个内置客户端工具：
    - ClickElementTool : 点击元素
    - InputElementTool : 输入文本
    - ScreenshotTool : 截图
    - GetDomTool : 获取 DOM
    - ScrollTool : 滚动
    - WaitTool : 等待

执行流程：
    AgentRuntime 调用 client_tool.execute(params, context) →
    client_tool 通过 context.execution_callback(tool_name, params) 回调
    测试执行引擎 → 引擎执行 Playwright 操作 → 返回 ToolResult →
    AgentRuntime 将结果注入 LLM 下一轮消息。
"""
from __future__ import annotations

from typing import Any, Dict

from app.services.agent.exceptions import ToolExecutionError
from app.services.agent.tools.base_tool import Tool, ToolContext, ToolResult


class _BaseClientTool(Tool):
    """客户端工具基类，统一处理 execution_callback 调用与异常。"""

    is_client_side = True

    async def _invoke_callback(
        self,
        params: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        """统一调用 execution_callback 并处理异常。"""
        if context.execution_callback is None:
            return ToolResult(
                success=False,
                error=f"客户端工具 {self.name} 需要 execution_callback，但当前会话未提供",
            )
        try:
            result = await context.execution_callback(self.name, params)
            if not isinstance(result, ToolResult):
                return ToolResult(
                    success=False,
                    error=f"execution_callback 返回类型错误: {type(result).__name__}",
                )
            return result
        except ToolExecutionError:
            raise
        except Exception as e:
            return ToolResult(success=False, error=f"{type(e).__name__}: {e}")


class ClickElementTool(_BaseClientTool):
    """点击元素。"""

    name = "click_element"
    description = "点击页面上指定选择器匹配的元素"
    parameters_schema = {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS/XPath 选择器"},
            "button": {"type": "string", "description": "鼠标按键: left/right/middle", "default": "left"},
        },
        "required": ["selector"],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return await self._invoke_callback(params, context)


class InputElementTool(_BaseClientTool):
    """输入文本。"""

    name = "input_element"
    description = "在指定输入框中输入文本"
    parameters_schema = {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS/XPath 选择器"},
            "text": {"type": "string", "description": "要输入的文本"},
            "clear_first": {"type": "boolean", "description": "是否先清空输入框", "default": True},
        },
        "required": ["selector", "text"],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return await self._invoke_callback(params, context)


class ScreenshotTool(_BaseClientTool):
    """截图。"""

    name = "screenshot"
    description = "截取当前页面截图，返回图片 URL"
    parameters_schema = {
        "type": "object",
        "properties": {
            "full_page": {"type": "boolean", "description": "是否截取整页", "default": False},
        },
        "required": [],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return await self._invoke_callback(params, context)


class GetDomTool(_BaseClientTool):
    """获取 DOM。"""

    name = "get_dom"
    description = "获取当前页面 DOM 序列化，可选指定选择器范围"
    parameters_schema = {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "限定 DOM 范围的选择器；省略则取整页"},
        },
        "required": [],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return await self._invoke_callback(params, context)


class ScrollTool(_BaseClientTool):
    """滚动页面。"""

    name = "scroll"
    description = "按像素偏移滚动页面"
    parameters_schema = {
        "type": "object",
        "properties": {
            "dx": {"type": "integer", "description": "水平滚动像素，正值向右", "default": 0},
            "dy": {"type": "integer", "description": "垂直滚动像素，正值向下", "default": 0},
        },
        "required": [],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return await self._invoke_callback(params, context)


class WaitTool(_BaseClientTool):
    """等待。"""

    name = "wait"
    description = "等待指定秒数或直到元素出现"
    parameters_schema = {
        "type": "object",
        "properties": {
            "seconds": {"type": "number", "description": "等待秒数", "default": 1.0},
            "selector": {"type": "string", "description": "等待元素出现的选择器；省略则固定等待 seconds 秒"},
        },
        "required": [],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return await self._invoke_callback(params, context)


__all__ = [
    "ClickElementTool",
    "InputElementTool",
    "ScreenshotTool",
    "GetDomTool",
    "ScrollTool",
    "WaitTool",
]
