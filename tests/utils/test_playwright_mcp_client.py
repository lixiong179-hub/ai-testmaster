import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.utils.playwright_mcp_client import PlaywrightMCPClient


class TestPlaywrightMCPClientInit:
    def test_defaults(self):
        client = PlaywrightMCPClient()
        assert client._server_command == "npx"
        assert client._port is None
        assert client._connected is False
        assert client._request_id == 0

    def test_custom(self):
        client = PlaywrightMCPClient(server_command="node", port=8080)
        assert client._server_command == "node"
        assert client._port == 8080


class TestPlaywrightMCPClientIsAvailable:
    def test_not_connected(self):
        client = PlaywrightMCPClient()
        assert client.is_available is False

    def test_connected_with_process(self):
        client = PlaywrightMCPClient()
        client._connected = True
        mock_process = MagicMock()
        mock_process.returncode = None
        client._process = mock_process
        assert client.is_available is True

    def test_connected_but_process_dead(self):
        client = PlaywrightMCPClient()
        client._connected = True
        mock_process = MagicMock()
        mock_process.returncode = 1
        client._process = mock_process
        assert client.is_available is False


class TestPlaywrightMCPClientStart:
    @pytest.mark.asyncio
    async def test_start_failure(self):
        client = PlaywrightMCPClient()
        with patch("asyncio.create_subprocess_exec", side_effect=Exception("no npx")):
            result = await client.start()
            assert result is False

    @pytest.mark.asyncio
    async def test_start_process_exits_immediately(self):
        client = PlaywrightMCPClient()
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdin = MagicMock()
        with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.start()
            assert result is False


class TestPlaywrightMCPClientStop:
    @pytest.mark.asyncio
    async def test_stop_no_process(self):
        client = PlaywrightMCPClient()
        await client.stop()
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_stop_with_process(self):
        client = PlaywrightMCPClient()
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.stdin = MagicMock()
        mock_process.stdin.close = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()
        client._process = mock_process
        client._connected = True
        await client.stop()
        assert client._connected is False
        assert client._process is None

    @pytest.mark.asyncio
    async def test_stop_process_timeout(self):
        client = PlaywrightMCPClient()
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.stdin = MagicMock()
        mock_process.stdin.close = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock(side_effect=__import__("asyncio").TimeoutError())
        mock_process.kill = MagicMock()
        client._process = mock_process
        client._connected = True
        await client.stop()
        mock_process.kill.assert_called_once()


class TestPlaywrightMCPClientSendRequest:
    @pytest.mark.asyncio
    async def test_send_request_no_process(self):
        client = PlaywrightMCPClient()
        result = await client._send_request("test_method", {})
        assert result is None

    @pytest.mark.asyncio
    async def test_send_request_dead_process(self):
        client = PlaywrightMCPClient()
        mock_process = MagicMock()
        mock_process.returncode = 1
        client._process = mock_process
        result = await client._send_request("test_method", {})
        assert result is None


class TestPlaywrightMCPClientSendNotification:
    @pytest.mark.asyncio
    async def test_send_notification_no_process(self):
        client = PlaywrightMCPClient()
        await client._send_notification("test_method", {})

    @pytest.mark.asyncio
    async def test_send_notification_dead_process(self):
        client = PlaywrightMCPClient()
        mock_process = MagicMock()
        mock_process.returncode = 1
        client._process = mock_process
        await client._send_notification("test_method", {})


class TestPlaywrightMCPClientCallTool:
    @pytest.mark.asyncio
    async def test_call_tool_text_content_json(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_send_request", return_value={
            "content": [{"type": "text", "text": '{"key": "value"}'}]
        }):
            result = await client._call_tool("test_tool", {})
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_call_tool_text_content_plain(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_send_request", return_value={
            "content": [{"type": "text", "text": "plain text"}]
        }):
            result = await client._call_tool("test_tool", {})
            assert result == "plain text"

    @pytest.mark.asyncio
    async def test_call_tool_no_content(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_send_request", return_value={"other": "data"}):
            result = await client._call_tool("test_tool", {})
            assert result == {"other": "data"}

    @pytest.mark.asyncio
    async def test_call_tool_none_result(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_send_request", return_value=None):
            result = await client._call_tool("test_tool", {})
            assert result is None

    @pytest.mark.asyncio
    async def test_call_tool_non_text_content(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_send_request", return_value={
            "content": [{"type": "image", "data": "base64data"}]
        }):
            result = await client._call_tool("test_tool", {})
            assert result == ""


class TestPlaywrightMCPClientBrowserMethods:
    @pytest.mark.asyncio
    async def test_browser_snapshot_string(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value="snapshot text"):
            result = await client.browser_snapshot()
            assert result == "snapshot text"

    @pytest.mark.asyncio
    async def test_browser_snapshot_dict(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value={"key": "value"}):
            result = await client.browser_snapshot()
            assert isinstance(result, str)
            assert "key" in result

    @pytest.mark.asyncio
    async def test_browser_click(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value={"ok": True}) as mock:
            await client.browser_click("button", ref="abc")
            mock.assert_called_once_with("browser_click", {"element": "button", "ref": "abc"})

    @pytest.mark.asyncio
    async def test_browser_click_no_ref(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value={"ok": True}) as mock:
            await client.browser_click("button")
            mock.assert_called_once_with("browser_click", {"element": "button"})

    @pytest.mark.asyncio
    async def test_browser_type(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value={"ok": True}) as mock:
            await client.browser_type("input", "hello", ref="xyz")
            mock.assert_called_once_with("browser_type", {"element": "input", "text": "hello", "ref": "xyz"})

    @pytest.mark.asyncio
    async def test_browser_navigate(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value={"ok": True}) as mock:
            await client.browser_navigate("https://example.com")
            mock.assert_called_once_with("browser_navigate", {"url": "https://example.com"})

    @pytest.mark.asyncio
    async def test_browser_screenshot_with_data(self):
        import base64
        client = PlaywrightMCPClient()
        fake_data = base64.b64encode(b"fake_image").decode()
        with patch.object(client, "_call_tool", return_value={"data": fake_data}):
            result = await client.browser_screenshot()
            assert result == b"fake_image"

    @pytest.mark.asyncio
    async def test_browser_screenshot_no_data(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value="not a dict"):
            result = await client.browser_screenshot()
            assert result is None

    @pytest.mark.asyncio
    async def test_browser_select_option(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value={"ok": True}) as mock:
            await client.browser_select_option("select", ["opt1"], ref="r1")
            mock.assert_called_once_with("browser_select_option", {"element": "select", "values": ["opt1"], "ref": "r1"})

    @pytest.mark.asyncio
    async def test_browser_hover(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value={"ok": True}) as mock:
            await client.browser_hover("element", ref="r1")
            mock.assert_called_once_with("browser_hover", {"element": "element", "ref": "r1"})

    @pytest.mark.asyncio
    async def test_browser_press_key(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value={"ok": True}) as mock:
            await client.browser_press_key("Enter")
            mock.assert_called_once_with("browser_press_key", {"key": "Enter"})

    @pytest.mark.asyncio
    async def test_browser_wait_for_time(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value={"ok": True}) as mock:
            await client.browser_wait_for(time=2.0)
            mock.assert_called_once_with("browser_wait_for", {"time": 2.0})

    @pytest.mark.asyncio
    async def test_browser_wait_for_text(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "_call_tool", return_value={"ok": True}) as mock:
            await client.browser_wait_for(text="loaded")
            mock.assert_called_once_with("browser_wait_for", {"text": "loaded"})


class TestPlaywrightMCPClientHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_not_available(self):
        client = PlaywrightMCPClient()
        result = await client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_available(self):
        client = PlaywrightMCPClient()
        client._connected = True
        mock_process = MagicMock()
        mock_process.returncode = None
        client._process = mock_process
        with patch.object(client, "_send_request", return_value={"tools": []}):
            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        client = PlaywrightMCPClient()
        client._connected = True
        mock_process = MagicMock()
        mock_process.returncode = None
        client._process = mock_process
        with patch.object(client, "_send_request", side_effect=Exception("error")):
            result = await client.health_check()
            assert result is False


class TestPlaywrightMCPClientReconnect:
    @pytest.mark.asyncio
    async def test_reconnect_success(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "stop", new_callable=AsyncMock), \
             patch.object(client, "start", new_callable=AsyncMock, return_value=True):
            result = await client.reconnect(max_retries=1)
            assert result is True

    @pytest.mark.asyncio
    async def test_reconnect_failure(self):
        client = PlaywrightMCPClient()
        with patch.object(client, "stop", new_callable=AsyncMock), \
             patch.object(client, "start", new_callable=AsyncMock, return_value=False), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.reconnect(max_retries=1)
            assert result is False
