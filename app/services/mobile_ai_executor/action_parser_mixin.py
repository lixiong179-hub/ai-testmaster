"""移动端AI动作解析Mixin - 自然语言描述到动作类型的解析。"""
import re
from typing import Optional

from app.services.mobile_ai_executor.types import MobileActionType


class MobileActionParserMixin:
    """动作解析：将自然语言描述映射为 MobileActionType。"""

    def parse_action(self, description: str) -> MobileActionType:
        desc = description.lower().strip()
        if any(kw in desc for kw in ["返回", "后退", "back"]):
            return MobileActionType.GO_BACK
        if any(kw in desc for kw in ["主页", "首页", "home", "桌面"]):
            if "导航" not in desc and "跳转" not in desc:
                return MobileActionType.GO_HOME
        if any(kw in desc for kw in ["向上滑动", "上滑", "scroll up", "向上滚动"]):
            return MobileActionType.SCROLL_UP
        if any(kw in desc for kw in ["向下滑动", "下滑", "scroll down", "向下滚动"]):
            return MobileActionType.SCROLL_DOWN
        if any(kw in desc for kw in ["向左滑动", "左滑", "scroll left"]):
            return MobileActionType.SCROLL_LEFT
        if any(kw in desc for kw in ["向右滑动", "右滑", "scroll right"]):
            return MobileActionType.SCROLL_RIGHT
        if any(kw in desc for kw in ["输入", "填写", "填入", "键入", "input", "type"]):
            return MobileActionType.INPUT
        if any(kw in desc for kw in ["滑动", "swipe"]):
            return MobileActionType.SWIPE
        if any(kw in desc for kw in ["按键", "按", "press"]):
            return MobileActionType.PRESS_KEY
        if any(kw in desc for kw in ["启动", "打开应用", "launch", "open app"]):
            return MobileActionType.LAUNCH_APP
        if any(kw in desc for kw in ["等待", "wait"]):
            return MobileActionType.WAIT
        if any(kw in desc for kw in ["验证", "检查", "确认", "verify", "check", "assert"]):
            return MobileActionType.VERIFY
        return MobileActionType.CLICK

    def _extract_input_text(self, description: str) -> Optional[str]:
        patterns = [
            r"输入[\"\"'](.+?)[\"\"']",
            r"输入(.+?)(?:到|进|入|$)",
            r"填写[\"\"'](.+?)[\"\"']",
            r"填写(.+?)(?:到|进|入|$)",
            r"键入[\"\"'](.+?)[\"\"']",
            r"type\s+[\"'](.+?)[\"']",
            r"input\s+[\"'](.+?)[\"']",
        ]
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return match.group(1).strip()
        return None

    def _extract_input_target(self, description: str) -> Optional[str]:
        patterns = [
            r"在(.+?)中输入",
            r"在(.+?)里输入",
            r"在(.+?)上输入",
            r"在(.+?)输入",
            r"在(.+?)中填写",
            r"在(.+?)里填写",
        ]
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return match.group(1).strip()
        return None

    def _extract_package_activity(self, description: str) -> Optional[tuple]:
        match = re.search(r"([\w.]+)/([\w.]+)", description)
        if match:
            package, activity = match.group(1), match.group(2)
            if re.match(r'^[a-zA-Z]', package) and re.match(r'^\.?[a-zA-Z]', activity):
                return package, activity
        return None
