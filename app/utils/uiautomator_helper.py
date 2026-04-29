import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from loguru import logger


class UIAutomatorError(Exception):
    pass


class ElementNotFoundError(UIAutomatorError):
    pass


@dataclass
class UIElement:
    resource_id: Optional[str] = None
    accessibility_id: Optional[str] = None
    text: Optional[str] = None
    content_desc: Optional[str] = None
    class_name: Optional[str] = None
    package: Optional[str] = None
    bounds: Optional[Dict[str, int]] = None
    clickable: bool = False
    enabled: bool = True
    focused: bool = False
    scrollable: bool = False

    @property
    def center(self) -> Optional[Dict[str, int]]:
        if not self.bounds:
            return None
        return {
            "x": (self.bounds["left"] + self.bounds["right"]) // 2,
            "y": (self.bounds["top"] + self.bounds["bottom"]) // 2
        }

    @property
    def width(self) -> int:
        if not self.bounds:
            return 0
        return self.bounds["right"] - self.bounds["left"]

    @property
    def height(self) -> int:
        if not self.bounds:
            return 0
        return self.bounds["bottom"] - self.bounds["top"]

    def matches_description(self, description: str) -> bool:
        desc_lower = description.lower()
        if self.text and self.text.lower() in desc_lower:
            return True
        if self.content_desc and self.content_desc.lower() in desc_lower:
            return True
        if self.accessibility_id and self.accessibility_id.lower() in desc_lower:
            return True
        if self.resource_id:
            id_part = self.resource_id.split(":id/")[-1] if ":id/" in self.resource_id else self.resource_id
            if id_part.lower() in desc_lower:
                return True
        return False


class UIAutomatorHelper:
    DUMP_PATH = "/sdcard/window_dump.xml"

    def __init__(self, adb_controller):
        self.adb = adb_controller

    async def dump_page(self) -> List[UIElement]:
        try:
            await self.adb._execute_command(
                "shell", "uiautomator", "dump", self.DUMP_PATH,
                check=False, timeout=15
            )
            cmd = self.adb._build_command("shell", "cat", self.DUMP_PATH)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=15
            )
            xml_content = stdout.decode("utf-8", errors="replace")
            if not xml_content or "<hierarchy" not in xml_content:
                raise UIAutomatorError("UIAutomator dump returned empty or invalid XML")
            try:
                await self.adb._execute_command(
                    "shell", "rm", "-f", self.DUMP_PATH,
                    check=False, timeout=5
                )
            except Exception:
                pass
            return self._parse_xml(xml_content)
        except asyncio.TimeoutError:
            raise UIAutomatorError("UIAutomator dump timed out")
        except Exception as e:
            if isinstance(e, UIAutomatorError):
                raise
            raise UIAutomatorError(f"UIAutomator dump failed: {e}")

    def _parse_xml(self, xml_content: str) -> List[UIElement]:
        elements = []
        try:
            sanitized = self._sanitize_xml(xml_content)
            root = ET.fromstring(sanitized)
            for node in root.iter():
                element = self._parse_node(node)
                if element:
                    elements.append(element)
        except ET.ParseError as e:
            raise UIAutomatorError(f"XML parse error: {e}")
        return elements

    @staticmethod
    def _sanitize_xml(xml_content: str) -> str:
        sanitized = re.sub(r'<!DOCTYPE[^>]*\[[^\]]*\]>', '', xml_content)
        sanitized = re.sub(r'<!DOCTYPE[^>]*>', '', sanitized)
        sanitized = re.sub(r'<!ENTITY[^>]*>', '', sanitized)
        return sanitized

    def _parse_node(self, node: ET.Element) -> Optional[UIElement]:
        bounds_str = node.get("bounds", "")
        bounds = self._parse_bounds(bounds_str)
        return UIElement(
            resource_id=node.get("resource-id") or None,
            accessibility_id=node.get("content-desc") or None,
            text=node.get("text") or None,
            content_desc=node.get("content-desc") or None,
            class_name=node.get("class") or None,
            package=node.get("package") or None,
            bounds=bounds,
            clickable=node.get("clickable") == "true",
            enabled=node.get("enabled") != "false",
            focused=node.get("focused") == "true",
            scrollable=node.get("scrollable") == "true",
        )

    def _parse_bounds(self, bounds_str: str) -> Optional[Dict[str, int]]:
        match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
        if match:
            return {
                "left": int(match.group(1)),
                "top": int(match.group(2)),
                "right": int(match.group(3)),
                "bottom": int(match.group(4)),
            }
        return None

    async def find_element(
        self,
        accessibility_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        text: Optional[str] = None,
        content_desc: Optional[str] = None,
    ) -> Optional[UIElement]:
        elements = await self.dump_page()
        for el in elements:
            if accessibility_id and el.accessibility_id == accessibility_id:
                return el
            if resource_id and el.resource_id == resource_id:
                return el
            if text and el.text == text:
                return el
            if content_desc and el.content_desc == content_desc:
                return el
        return None

    async def find_elements_by_description(self, description: str) -> List[UIElement]:
        elements = await self.dump_page()
        return [el for el in elements if el.matches_description(description)]

    async def find_element_by_text(self, text: str) -> Optional[UIElement]:
        return await self.find_element(text=text)

    async def find_element_by_resource_id(self, resource_id: str) -> Optional[UIElement]:
        return await self.find_element(resource_id=resource_id)

    async def click_element(
        self,
        accessibility_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        text: Optional[str] = None,
    ) -> bool:
        element = await self.find_element(
            accessibility_id=accessibility_id,
            resource_id=resource_id,
            text=text,
        )
        if not element or not element.center:
            return False
        await self.adb.click(element.center["x"], element.center["y"])
        return True

    async def get_clickable_elements(self) -> List[UIElement]:
        elements = await self.dump_page()
        return [el for el in elements if el.clickable and el.enabled]

    async def get_element_at_coordinates(self, x: int, y: int) -> Optional[UIElement]:
        elements = await self.dump_page()
        for el in elements:
            if el.bounds and el.bounds["left"] <= x <= el.bounds["right"] and el.bounds["top"] <= y <= el.bounds["bottom"]:
                return el
        return None

    async def extract_locator_from_coordinates(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        element = await self.get_element_at_coordinates(x, y)
        if not element:
            return None
        locator = {"bounds": element.bounds}
        if element.resource_id:
            locator["resource_id"] = element.resource_id
        if element.accessibility_id:
            locator["accessibility_id"] = element.accessibility_id
        if element.text:
            locator["text"] = element.text
        if element.content_desc:
            locator["content_desc"] = element.content_desc
        if element.class_name:
            locator["class_name"] = element.class_name
        return locator
