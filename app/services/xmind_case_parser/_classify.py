import re
from typing import Any
from dataclasses import dataclass, field


@dataclass
class TopicNode:
    title: str
    priority: int | None = None
    notes: str = ""
    children: list["TopicNode"] = field(default_factory=list)


class _ClassifyMixin:
    PRECONDITION_HINTS = (
        "有",
        "无",
        "未",
        "已",
        "默认",
        "从",
        "支持",
        "当前",
        "存在",
        "不存在",
        "有记录",
        "无记录",
        "有内容",
        "无内容",
        "有教材",
        "无网络",
    )
    ACTION_PATTERNS = (
        "点击",
        "选择",
        "勾选",
        "输入",
        "提交",
        "删除",
        "确认",
        "取消",
        "修改",
        "播放",
        "收藏",
        "切换",
        "清空",
        "关闭",
        "检查",
        "开始",
        "继续",
        "返回",
        "退出",
        "查看",
        "重试",
        "编辑",
    )
    EXPECTED_PATTERNS = (
        "界面显示",
        "界面提示",
        "提示",
        "显示",
        "置灰",
        "不可点击",
        "成功",
        "失败",
        "跳转",
        "进入",
        "仍然",
        "返回到",
        "toast",
        "弹窗",
        "自动",
        "不出现",
        "出现",
        "倒计时",
        "切换为",
    )
    IGNORE_PATTERNS = (
        "界面详见UI",
        "界面参照UI",
        "界面显示见UI",
        "详见UI",
        "参照UI",
    )

    def _classify_text(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return "ignore"
        if any(pattern in normalized for pattern in self.IGNORE_PATTERNS):
            return "ignore"
        if normalized.startswith(self.PRECONDITION_HINTS):
            return "condition"
        if any(pattern in normalized for pattern in self.ACTION_PATTERNS):
            return "action"
        if any(pattern in normalized for pattern in self.EXPECTED_PATTERNS):
            return "expected"
        if re.match(r"^\d+[.、]", normalized):
            return "action"
        return "other"

    def _infer_case_title(
        self,
        texts: list[str],
        actions: list[str],
        expected_result: str,
        module_name: str,
    ) -> str:
        if actions and expected_result:
            title = f"{actions[-1]}，{expected_result}"
        elif actions:
            title = actions[-1]
        elif expected_result:
            title = expected_result
        elif texts:
            title = texts[0]
        else:
            title = module_name
        return self._truncate_field(title, self.TITLE_MAX_LEN)

    def _infer_function_name(self, texts: list[str], module_name: str) -> str:
        if len(texts) >= 2:
            return self._truncate_field(texts[1], self.TITLE_MAX_LEN)
        return ""

    def _build_steps(self, actions: list[str], overall_expected: str) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        for index, action in enumerate(actions, start=1):
            steps.append(
                {
                    "step": index,
                    "action": action,
                    "expected_result": overall_expected if index == len(actions) else "",
                    "param": "",
                }
            )
        return steps

    def _infer_priority(self, segments: list[TopicNode]) -> int:
        for segment in reversed(segments):
            if segment.priority is not None:
                return segment.priority
        return 2
