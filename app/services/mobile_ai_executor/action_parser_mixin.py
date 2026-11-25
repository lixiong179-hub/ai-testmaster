"""移动端AI动作解析Mixin - 自然语言描述到动作类型的解析。"""

import re

from app.services.mobile_ai_executor.types import MobileActionType

_GO_BACK_KEYWORDS: tuple[str, ...] = ("返回", "后退", "back")
_HOME_KEYWORDS: tuple[str, ...] = ("主页", "首页", "home", "桌面")
_NAVIGATION_KEYWORDS: tuple[str, ...] = ("导航", "跳转")

# 顺序即优先级：滑动类必须先于通用「滑动/swipe」判定，否则会被降级为 SWIPE。
_KEYWORD_RULES: tuple[tuple[tuple[str, ...], MobileActionType], ...] = (
    (("向上滑动", "上滑", "scroll up", "向上滚动"), MobileActionType.SCROLL_UP),
    (("向下滑动", "下滑", "scroll down", "向下滚动"), MobileActionType.SCROLL_DOWN),
    (("向左滑动", "左滑", "scroll left"), MobileActionType.SCROLL_LEFT),
    (("向右滑动", "右滑", "scroll right"), MobileActionType.SCROLL_RIGHT),
    (("输入", "填写", "填入", "键入", "input", "type"), MobileActionType.INPUT),
    (("滑动", "swipe"), MobileActionType.SWIPE),
    (("按键", "按", "press"), MobileActionType.PRESS_KEY),
    (("启动", "打开应用", "launch", "open app"), MobileActionType.LAUNCH_APP),
    (("等待", "wait"), MobileActionType.WAIT),
    (("验证", "检查", "确认", "verify", "check", "assert"), MobileActionType.VERIFY),
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


class MobileActionParserMixin:
    """动作解析：将自然语言描述映射为 MobileActionType。"""

    def parse_action(self, description: str) -> MobileActionType:
        desc = description.lower().strip()
        if _contains_any(desc, _GO_BACK_KEYWORDS):
            return MobileActionType.GO_BACK
        if self._is_home_command(desc):
            return MobileActionType.GO_HOME
        return self._match_keyword_rule(desc)

    @staticmethod
    def _is_home_command(desc: str) -> bool:
        """仅当描述不含「导航/跳转」时才算回主页，避免把导航动作误判为 HOME。"""
        return _contains_any(desc, _HOME_KEYWORDS) and not _contains_any(desc, _NAVIGATION_KEYWORDS)

    @staticmethod
    def _match_keyword_rule(desc: str) -> MobileActionType:
        for keywords, action_type in _KEYWORD_RULES:
            if _contains_any(desc, keywords):
                return action_type
        return MobileActionType.CLICK

    def _extract_input_text(self, description: str) -> str | None:
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

    def _extract_input_target(self, description: str) -> str | None:
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

    def _extract_package_activity(self, description: str) -> tuple | None:
        match = re.search(r"([\w.]+)/([\w.]+)", description)
        if match:
            package, activity = match.group(1), match.group(2)
            if re.match(r"^[a-zA-Z]", package) and re.match(r"^\.?[a-zA-Z]", activity):
                return package, activity
        return None
