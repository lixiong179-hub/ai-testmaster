"""MCP识别器 - 通过MCP协议与外部识别服务交互实现元素识别。
"""
import json
from typing import Optional, List

from loguru import logger

from app.interfaces.element_recognizer import ElementRecognizer, RecognitionResult
from app.utils.playwright_mcp_client import PlaywrightMCPClient, get_mcp_client
from app.utils.mcp_text_llm import MCPAwareLLM, get_mcp_llm


class MCPRecognizer(ElementRecognizer):

    def __init__(self, mcp_client: Optional[PlaywrightMCPClient] = None, mcp_llm: Optional[MCPAwareLLM] = None) -> None:
        self._mcp_client = mcp_client
        self._mcp_llm = mcp_llm

    @property
    def name(self) -> str:
        return "mcp"

    async def is_available(self) -> bool:
        client = await self._get_mcp_client()
        return client is not None and client.is_available

    async def _get_mcp_client(self) -> Optional[PlaywrightMCPClient]:
        if self._mcp_client is None:
            try:
                self._mcp_client = await get_mcp_client()
            except Exception:
                self._mcp_client = None
        return self._mcp_client

    def _get_mcp_llm(self) -> MCPAwareLLM:
        if self._mcp_llm is None:
            self._mcp_llm = get_mcp_llm()
        return self._mcp_llm

    async def recognize(self, browser, operation_description: str, action_type: Optional[str] = None) -> RecognitionResult:
        mcp_client = await self._get_mcp_client()
        if not mcp_client or not mcp_client.is_available:
            logger.warning("MCP客户端不可用，降级到视觉模型")
            return RecognitionResult(
                locator_type="mcp",
                locator_value="",
                confidence=0,
                raw_result={"error": "MCP客户端不可用"}
            )

        try:
            snapshot = await mcp_client.browser_snapshot()
        except Exception as e:
            logger.error(f"获取Accessibility Tree失败: {e}")
            return RecognitionResult(
                locator_type="mcp",
                locator_value="",
                confidence=0,
                raw_result={"error": "获取页面快照失败"}
            )

        if not snapshot:
            return RecognitionResult(
                locator_type="mcp",
                locator_value="",
                confidence=0,
                raw_result={"error": "Accessibility Tree为空"}
            )

        snapshot_str = snapshot if isinstance(snapshot, str) else json.dumps(snapshot, ensure_ascii=False)

        mcp_llm = self._get_mcp_llm()
        locator_result = await mcp_llm.understand_operation(snapshot_str, operation_description, action_type)

        if not locator_result:
            return RecognitionResult(
                locator_type="mcp",
                locator_value="",
                confidence=0,
                raw_result={"snapshot_size": len(snapshot_str)}
            )

        locator_type = locator_result.get("locator_type", "")
        locator_value = locator_result.get("locator_value", "")
        confidence = locator_result.get("confidence", 0)

        return RecognitionResult(
            locator_type=locator_type,
            locator_value=locator_value,
            confidence=confidence,
            raw_result=locator_result,
            element_info={
                "locator_type": locator_type,
                "locator_value": locator_value,
                "element_description": locator_result.get("element_description", ""),
                "reasoning": locator_result.get("reasoning", ""),
                "snapshot_size": len(snapshot_str)
            }
        )

    async def batch_recognize(self, browser, operations: List[str]) -> List[RecognitionResult]:
        mcp_client = await self._get_mcp_client()
        if not mcp_client or not mcp_client.is_available:
            return [
                RecognitionResult(locator_type="mcp", locator_value="", confidence=0,
                                  raw_result={"error": "MCP客户端不可用"})
                for _ in operations
            ]

        try:
            snapshot = await mcp_client.browser_snapshot()
        except Exception as e:
            logger.error(f"批量识别获取Accessibility Tree失败: {e}")
            return [
                RecognitionResult(locator_type="mcp", locator_value="", confidence=0,
                                  raw_result={"error": "获取页面快照失败"})
                for _ in operations
            ]

        if not snapshot:
            return [
                RecognitionResult(locator_type="mcp", locator_value="", confidence=0)
                for _ in operations
            ]

        snapshot_str = snapshot if isinstance(snapshot, str) else json.dumps(snapshot, ensure_ascii=False)

        mcp_llm = self._get_mcp_llm()
        llm_results = await mcp_llm.batch_understand_operations(snapshot_str, operations)

        results = []
        for llm_result in llm_results:
            if llm_result:
                results.append(RecognitionResult(
                    locator_type=llm_result.get("locator_type", ""),
                    locator_value=llm_result.get("locator_value", ""),
                    confidence=llm_result.get("confidence", 0),
                    raw_result=llm_result,
                    element_info={
                        "locator_type": llm_result.get("locator_type", ""),
                        "locator_value": llm_result.get("locator_value", ""),
                        "element_description": llm_result.get("element_description", ""),
                    }
                ))
            else:
                results.append(RecognitionResult(
                    locator_type="mcp", locator_value="", confidence=0
                ))

        return results

    async def execute_action(self, result: RecognitionResult, action_type: str = "click", input_value: Optional[str] = None) -> bool:
        mcp_client = await self._get_mcp_client()
        if not mcp_client or not mcp_client.is_available:
            logger.warning("MCP客户端不可用，无法执行操作")
            return False

        locator_type = result.locator_type
        locator_value = result.locator_value

        if not locator_value and action_type != "wait":
            logger.warning(f"定位值为空，无法执行操作: action_type={action_type}")
            return False

        try:
            element = ""
            ref = None
            if locator_type == "ref":
                ref = locator_value
            else:
                element = locator_value

            def _mask_sensitive(val: Optional[str]) -> str:
                if not val:
                    return ""
                if len(val) <= 2:
                    return "***"
                return val[0] + "***" + val[-1]

            if action_type == "click":
                logger.info(f"MCP执行click: element={element}, ref={ref}")
                await mcp_client.browser_click(element, ref=ref)
            elif action_type in ("input", "type"):
                if not input_value:
                    logger.warning("type操作缺少input_value参数")
                    return False
                logger.info(f"MCP执行type: element={element}, ref={ref}, text={_mask_sensitive(input_value)}")
                await mcp_client.browser_type(element, input_value, ref=ref)
            elif action_type == "hover":
                logger.info(f"MCP执行hover: element={element}, ref={ref}")
                await mcp_client.browser_hover(element, ref=ref)
            elif action_type == "select":
                if not input_value:
                    logger.warning("select操作缺少input_value参数")
                    return False
                values = [v.strip() for v in input_value.split(",")]
                logger.info(f"MCP执行select: element={element}, ref={ref}, values={[_mask_sensitive(v) for v in values]}")
                await mcp_client.browser_select_option(element, values, ref=ref)
            elif action_type == "wait":
                wait_time = None
                wait_text = None
                if input_value:
                    try:
                        wait_time = float(input_value)
                    except ValueError:
                        wait_text = input_value
                logger.info(f"MCP执行wait: time={wait_time}, text={wait_text}")
                await mcp_client.browser_wait_for(time=wait_time, text=wait_text)
            else:
                logger.warning(f"不支持的操作类型: {action_type}")
                return False

            logger.info(f"MCP操作执行成功: action_type={action_type}, locator_type={locator_type}")
            return True
        except Exception as e:
            logger.error(f"MCP执行操作失败: action_type={action_type}, error={e}")
            return False
