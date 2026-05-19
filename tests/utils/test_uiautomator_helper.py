import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.utils.uiautomator_helper import (
    UIAutomatorError,
    ElementNotFoundError,
    UIElement,
    UIAutomatorHelper,
)


class TestUIAutomatorErrors:
    def test_ui_automator_error(self):
        with pytest.raises(UIAutomatorError):
            raise UIAutomatorError("test")

    def test_element_not_found_error(self):
        assert issubclass(ElementNotFoundError, UIAutomatorError)


class TestUIElement:
    def test_center(self):
        el = UIElement(bounds={"left": 0, "top": 0, "right": 100, "bottom": 200})
        assert el.center == {"x": 50, "y": 100}

    def test_center_no_bounds(self):
        el = UIElement()
        assert el.center is None

    def test_width(self):
        el = UIElement(bounds={"left": 10, "top": 20, "right": 110, "bottom": 220})
        assert el.width == 100

    def test_width_no_bounds(self):
        el = UIElement()
        assert el.width == 0

    def test_height(self):
        el = UIElement(bounds={"left": 10, "top": 20, "right": 110, "bottom": 220})
        assert el.height == 200

    def test_height_no_bounds(self):
        el = UIElement()
        assert el.height == 0

    def test_matches_description_by_text(self):
        el = UIElement(text="登录")
        assert el.matches_description("点击登录按钮") is True

    def test_matches_description_by_content_desc(self):
        el = UIElement(content_desc="提交")
        assert el.matches_description("点击提交按钮") is True

    def test_matches_description_by_accessibility_id(self):
        el = UIElement(accessibility_id="submit")
        assert el.matches_description("click submit button") is True

    def test_matches_description_by_resource_id(self):
        el = UIElement(resource_id="com.app:id/login_button")
        assert el.matches_description("login_button") is True

    def test_matches_description_by_resource_id_with_prefix(self):
        el = UIElement(resource_id="com.app:id/username")
        assert el.matches_description("username") is True

    def test_matches_description_no_match(self):
        el = UIElement(text="登录")
        assert el.matches_description("退出") is False

    def test_matches_description_empty_element(self):
        el = UIElement()
        assert el.matches_description("anything") is False

    def test_defaults(self):
        el = UIElement()
        assert el.resource_id is None
        assert el.clickable is False
        assert el.enabled is True
        assert el.focused is False
        assert el.scrollable is False


class TestUIAutomatorHelper:
    def test_parse_bounds_valid(self):
        helper = UIAutomatorHelper(MagicMock())
        result = helper._parse_bounds("[0,100][200,300]")
        assert result == {"left": 0, "top": 100, "right": 200, "bottom": 300}

    def test_parse_bounds_invalid(self):
        helper = UIAutomatorHelper(MagicMock())
        result = helper._parse_bounds("invalid")
        assert result is None

    def test_parse_bounds_empty(self):
        helper = UIAutomatorHelper(MagicMock())
        result = helper._parse_bounds("")
        assert result is None

    def test_parse_xml_valid(self):
        helper = UIAutomatorHelper(MagicMock())
        xml = '<hierarchy><node bounds="[0,0][100,200]" text="Hello" clickable="true" class="android.widget.Button" package="com.app" resource-id="com.app:id/btn" content-desc="btn" enabled="true" focused="false" scrollable="false"/></hierarchy>'
        elements = helper._parse_xml(xml)
        assert len(elements) >= 1
        text_elements = [e for e in elements if e.text == "Hello"]
        assert len(text_elements) == 1
        assert text_elements[0].clickable is True

    def test_parse_xml_invalid(self):
        helper = UIAutomatorHelper(MagicMock())
        with pytest.raises(UIAutomatorError, match="XML parse error"):
            helper._parse_xml("<invalid><>")

    def test_sanitize_xml_doctype(self):
        xml = '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe "test">]><hierarchy/>'
        result = UIAutomatorHelper._sanitize_xml(xml)
        assert "<!DOCTYPE" not in result
        assert "<!ENTITY" not in result

    def test_sanitize_xml_doctype_simple(self):
        xml = '<?xml version="1.0"?><!DOCTYPE foo><hierarchy/>'
        result = UIAutomatorHelper._sanitize_xml(xml)
        assert "<!DOCTYPE" not in result

    def test_parse_node(self):
        import xml.etree.ElementTree as ET
        helper = UIAutomatorHelper(MagicMock())
        node = ET.Element("node")
        node.set("bounds", "[10,20][110,220]")
        node.set("text", "Click Me")
        node.set("clickable", "true")
        node.set("class", "Button")
        node.set("resource-id", "com.app:id/btn")
        node.set("content-desc", "Submit")
        node.set("package", "com.app")
        node.set("enabled", "true")
        node.set("focused", "false")
        node.set("scrollable", "false")
        el = helper._parse_node(node)
        assert el is not None
        assert el.text == "Click Me"
        assert el.clickable is True
        assert el.bounds == {"left": 10, "top": 20, "right": 110, "bottom": 220}

    def test_parse_node_no_bounds(self):
        import xml.etree.ElementTree as ET
        helper = UIAutomatorHelper(MagicMock())
        node = ET.Element("node")
        el = helper._parse_node(node)
        assert el is not None
        assert el.bounds is None

    def test_parse_node_disabled(self):
        import xml.etree.ElementTree as ET
        helper = UIAutomatorHelper(MagicMock())
        node = ET.Element("node")
        node.set("enabled", "false")
        el = helper._parse_node(node)
        assert el.enabled is False

    @pytest.mark.asyncio
    async def test_find_element_by_text(self):
        helper = UIAutomatorHelper(MagicMock())
        xml = '<hierarchy><node text="Login" bounds="[0,0][100,50]"/><node text="Logout" bounds="[0,60][100,110]"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            el = await helper.find_element_by_text("Login")
            assert el is not None
            assert el.text == "Login"

    @pytest.mark.asyncio
    async def test_find_element_by_resource_id(self):
        helper = UIAutomatorHelper(MagicMock())
        xml = '<hierarchy><node resource-id="com.app:id/btn" bounds="[0,0][100,50]"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            el = await helper.find_element_by_resource_id("com.app:id/btn")
            assert el is not None

    @pytest.mark.asyncio
    async def test_find_element_not_found(self):
        helper = UIAutomatorHelper(MagicMock())
        xml = '<hierarchy><node text="Login" bounds="[0,0][100,50]"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            el = await helper.find_element(text="NonExistent")
            assert el is None

    @pytest.mark.asyncio
    async def test_find_elements_by_description(self):
        helper = UIAutomatorHelper(MagicMock())
        xml = '<hierarchy><node text="Login" bounds="[0,0][100,50]"/><node text="Logout" bounds="[0,60][100,110]"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            els = await helper.find_elements_by_description("Login")
            assert len(els) >= 1

    @pytest.mark.asyncio
    async def test_click_element(self):
        mock_adb = MagicMock()
        mock_adb.click = AsyncMock()
        helper = UIAutomatorHelper(mock_adb)
        xml = '<hierarchy><node text="Login" bounds="[0,0][100,50]" clickable="true"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            result = await helper.click_element(text="Login")
            assert result is True
            mock_adb.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_element_not_found(self):
        mock_adb = MagicMock()
        helper = UIAutomatorHelper(mock_adb)
        xml = '<hierarchy><node text="Login" bounds="[0,0][100,50]"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            result = await helper.click_element(text="NonExistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_clickable_elements(self):
        helper = UIAutomatorHelper(MagicMock())
        xml = '<hierarchy><node text="Btn1" clickable="true" enabled="true" bounds="[0,0][100,50]"/><node text="Label" clickable="false" bounds="[0,60][100,110]"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            els = await helper.get_clickable_elements()
            assert len(els) == 1
            assert els[0].text == "Btn1"

    @pytest.mark.asyncio
    async def test_get_element_at_coordinates(self):
        helper = UIAutomatorHelper(MagicMock())
        xml = '<hierarchy><node text="Btn1" bounds="[0,0][100,50]"/><node text="Btn2" bounds="[0,60][100,110]"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            el = await helper.get_element_at_coordinates(50, 25)
            assert el is not None
            assert el.text == "Btn1"

    @pytest.mark.asyncio
    async def test_get_element_at_coordinates_not_found(self):
        helper = UIAutomatorHelper(MagicMock())
        xml = '<hierarchy><node text="Btn1" bounds="[0,0][100,50]"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            el = await helper.get_element_at_coordinates(500, 500)
            assert el is None

    @pytest.mark.asyncio
    async def test_extract_locator_from_coordinates(self):
        helper = UIAutomatorHelper(MagicMock())
        xml = '<hierarchy><node text="Btn1" resource-id="com.app:id/btn" class="Button" bounds="[0,0][100,50]"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            locator = await helper.extract_locator_from_coordinates(50, 25)
            assert locator is not None
            assert locator["resource_id"] == "com.app:id/btn"
            assert locator["text"] == "Btn1"

    @pytest.mark.asyncio
    async def test_extract_locator_not_found(self):
        helper = UIAutomatorHelper(MagicMock())
        xml = '<hierarchy><node text="Btn1" bounds="[0,0][100,50]"/></hierarchy>'
        with patch.object(helper, "dump_page", return_value=helper._parse_xml(xml)):
            locator = await helper.extract_locator_from_coordinates(500, 500)
            assert locator is None

    @pytest.mark.asyncio
    async def test_dump_page_timeout(self):
        mock_adb = MagicMock()
        mock_adb._execute_command = AsyncMock(side_effect=__import__("asyncio").TimeoutError())
        mock_adb._build_command = MagicMock(return_value=["adb", "shell", "cat", "/sdcard/window_dump.xml"])
        helper = UIAutomatorHelper(mock_adb)
        with pytest.raises(UIAutomatorError, match="timed out"):
            await helper.dump_page()

    @pytest.mark.asyncio
    async def test_dump_page_failure(self):
        mock_adb = MagicMock()
        mock_adb._execute_command = AsyncMock(side_effect=Exception("adb error"))
        helper = UIAutomatorHelper(mock_adb)
        with pytest.raises(UIAutomatorError, match="failed"):
            await helper.dump_page()
