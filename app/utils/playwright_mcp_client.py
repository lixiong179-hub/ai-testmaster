import asyncio
import atexit
import base64
import json
from typing import Optional, Dict, Any, List

from loguru import logger


class PlaywrightMCPClient:

    def __init__(self, server_command: Optional[str] = None, port: Optional[int] = None):
        self._server_command = server_command or "npx"
        self._server_args = ["@playwright/mcp@latest"]
        self._port = port
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._connected = False

    async def start(self) -> bool:
        try:
            self._process = await asyncio.create_subprocess_exec(
                self._server_command,
                *self._server_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.sleep(2)
            if self._process.returncode is not None:
                logger.error(f"MCP Server启动失败，退出码: {self._process.returncode}")
                return False
            self._connected = True
            init_result = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ai-testmaster", "version": "1.0.0"}
            })
            if init_result:
                await self._send_notification("notifications/initialized", {})
                logger.info("Playwright MCP Server启动成功")
                return True
            return False
        except Exception as e:
            logger.error(f"MCP Server启动异常: {e}")
            self._connected = False
            return False

    async def stop(self):
        if self._process and self._process.returncode is None:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()
            except Exception as e:
                logger.error(f"MCP Server停止异常: {e}")
            finally:
                self._connected = False
                self._process = None

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._process or self._process.returncode is not None:
            logger.error("MCP Server未运行")
            return None
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params
        }
        try:
            message = json.dumps(request) + "\n"
            self._process.stdin.write(message.encode())
            await self._process.stdin.drain()
            target_id = self._request_id
            for _ in range(20):
                try:
                    response_line = await asyncio.wait_for(
                        self._process.stdout.readline(), timeout=30
                    )
                except asyncio.TimeoutError:
                    logger.error(f"MCP请求超时: {method}")
                    return None
                if not response_line:
                    return None
                line_str = response_line.decode().strip()
                if not line_str:
                    continue
                try:
                    response = json.loads(line_str)
                except json.JSONDecodeError:
                    logger.debug(f"跳过非JSON行: {line_str[:100]}")
                    continue
                if "id" not in response:
                    logger.debug(f"跳过MCP通知: {response.get('method', 'unknown')}")
                    continue
                if response.get("id") != target_id:
                    logger.debug(f"跳过不匹配的响应: 期望id={target_id}, 实际id={response.get('id')}")
                    continue
                if "error" in response:
                    logger.error(f"MCP请求错误: {response['error']}")
                    return None
                return response.get("result")
            logger.error("MCP响应中未找到匹配的响应")
            return None
        except Exception as e:
            logger.error(f"MCP请求异常: {e}")
            self._connected = False
            return None

    async def _send_notification(self, method: str, params: Dict[str, Any]):
        if not self._process or self._process.returncode is not None:
            return
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        try:
            message = json.dumps(notification) + "\n"
            self._process.stdin.write(message.encode())
            await self._process.stdin.drain()
        except Exception as e:
            logger.error(f"MCP通知发送异常: {e}")

    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Any]:
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        if result and "content" in result:
            contents = result["content"]
            if isinstance(contents, list) and len(contents) > 0:
                for content in contents:
                    if content.get("type") == "text":
                        try:
                            return json.loads(content["text"])
                        except (json.JSONDecodeError, TypeError):
                            return content["text"]
                return contents[0].get("text", "")
            return contents
        return result

    async def browser_snapshot(self) -> Optional[str]:
        result = await self._call_tool("browser_snapshot", {})
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False)
        return result

    async def browser_click(self, element: str, ref: Optional[str] = None) -> Optional[Any]:
        arguments = {"element": element}
        if ref:
            arguments["ref"] = ref
        return await self._call_tool("browser_click", arguments)

    async def browser_type(self, element: str, text: str, ref: Optional[str] = None) -> Optional[Any]:
        arguments = {"element": element, "text": text}
        if ref:
            arguments["ref"] = ref
        return await self._call_tool("browser_type", arguments)

    async def browser_navigate(self, url: str) -> Optional[Any]:
        return await self._call_tool("browser_navigate", {"url": url})

    async def browser_screenshot(self) -> Optional[bytes]:
        result = await self._call_tool("browser_screenshot", {})
        if isinstance(result, dict) and "data" in result:
            return base64.b64decode(result["data"])
        return None

    async def browser_select_option(self, element: str, values: List[str], ref: Optional[str] = None) -> Optional[Any]:
        arguments = {"element": element, "values": values}
        if ref:
            arguments["ref"] = ref
        return await self._call_tool("browser_select_option", arguments)

    async def browser_hover(self, element: str, ref: Optional[str] = None) -> Optional[Any]:
        arguments = {"element": element}
        if ref:
            arguments["ref"] = ref
        return await self._call_tool("browser_hover", arguments)

    async def browser_press_key(self, key: str) -> Optional[Any]:
        return await self._call_tool("browser_press_key", {"key": key})

    async def browser_wait_for(self, time: Optional[float] = None, text: Optional[str] = None) -> Optional[Any]:
        arguments = {}
        if time is not None:
            arguments["time"] = time
        if text is not None:
            arguments["text"] = text
        return await self._call_tool("browser_wait_for", arguments)

    @property
    def is_available(self) -> bool:
        return self._connected and self._process is not None and self._process.returncode is None

    async def health_check(self) -> bool:
        if not self.is_available:
            return False
        try:
            result = await self._send_request("tools/list", {})
            return result is not None
        except Exception:
            return False

    async def reconnect(self, max_retries: int = 3) -> bool:
        for attempt in range(max_retries):
            logger.info(f"MCP重连尝试 {attempt + 1}/{max_retries}")
            await self.stop()
            if await self.start():
                return True
            await asyncio.sleep(2)
        logger.error("MCP重连失败")
        return False


_mcp_client: Optional[PlaywrightMCPClient] = None


async def get_mcp_client() -> PlaywrightMCPClient:
    global _mcp_client
    if _mcp_client is None or not _mcp_client.is_available:
        _mcp_client = PlaywrightMCPClient()
        await _mcp_client.start()
    return _mcp_client


__all__ = [
    'PlaywrightMCPClient',
    'get_mcp_client',
]


def _cleanup_mcp_client():
    global _mcp_client
    if _mcp_client and _mcp_client._process and _mcp_client._process.returncode is None:
        try:
            _mcp_client._process.terminate()
        except Exception:
            pass

atexit.register(_cleanup_mcp_client)
