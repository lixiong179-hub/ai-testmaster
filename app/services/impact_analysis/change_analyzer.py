"""代码变更分析器（Phase 1 Task 4：Test Impact Analysis）

业务用途：解析 git diff 输出，识别变更文件与行范围，供影响映射查询。
设计原则：
1. 输入为 git diff 文本（unified format），纯函数无副作用；
2. 解析失败时返回空列表，不抛异常；
3. 支持多文件 diff 解析，按文件分组返回。

依赖：subprocess（执行 git diff）、re（解析 diff）
"""

import logging
import re
import subprocess
from dataclasses import dataclass, field

from app.services.impact_analysis.models import CodeChange

logger = logging.getLogger(__name__)

# git diff 行范围正则：@@ -a,b +c,d @@
# 同时捕获 old 文件起始行（group 1）和 new 文件起始行（group 2），
# 以便 deleted/added 行分别使用各自文件的行号，避免连续删除行号错位。
_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

# 文件级元信息行前缀（判定归属，不推进行号）
_FILE_META_PREFIXES = ("+++ b/", "+++ /dev/null", "--- a/", "--- /dev/null", "new file mode", "deleted file mode")


@dataclass
class _DiffParseState:
    """单文件 diff 解析的跨行累积状态。"""

    file_path: str | None = None
    added: set[int] = field(default_factory=set)
    deleted: set[int] = field(default_factory=set)
    is_new: bool = False
    is_deleted: bool = False
    old_line: int = 0
    new_line: int = 0


def _flush_diff_state(state: _DiffParseState, changes: list[CodeChange]) -> None:
    """把当前文件状态落成 CodeChange（无路径则跳过）。"""
    if state.file_path is None:
        return
    changes.append(
        CodeChange(
            file_path=state.file_path,
            added_lines=frozenset(state.added),
            deleted_lines=frozenset(state.deleted),
            is_new_file=state.is_new,
            is_deleted=state.is_deleted,
        )
    )


def _apply_hunk_header(line: str, state: _DiffParseState) -> None:
    """解析 `@@ -a,b +c,d @@`，重置两侧行号。"""
    match = _HUNK_HEADER_RE.match(line)
    if match is None:
        return
    state.old_line = int(match.group(1))
    state.new_line = int(match.group(2))


def _apply_file_header(line: str, state: _DiffParseState) -> None:
    """处理 `+++`/`---`/新增/删除文件等文件级元信息行。"""
    if line.startswith("new file mode"):
        state.is_new = True
    elif line.startswith("deleted file mode"):
        state.is_deleted = True
    elif line.startswith("+++ b/") or (line.startswith("--- a/") and state.file_path is None):
        state.file_path = line[6:]


def _record_added(line: str, state: _DiffParseState) -> None:
    """记录新增行号（`+++` 为文件头，不计数）。"""
    if line.startswith("+++") or not state.file_path:
        return
    state.added.add(state.new_line)
    state.new_line += 1


def _record_deleted(line: str, state: _DiffParseState) -> None:
    """记录删除行号（`---` 为文件头，不计数）。"""
    if line.startswith("---") or not state.file_path:
        return
    state.deleted.add(state.old_line)
    state.old_line += 1


def _advance_context_line(state: _DiffParseState) -> None:
    """上下文行同时推进新旧行号。"""
    if not state.file_path:
        return
    state.old_line += 1
    state.new_line += 1


def _apply_diff_line(line: str, state: _DiffParseState) -> None:
    """按行首分派：hunk 头→文件元信息→增/删/上下文行。"""
    if line.startswith("@@"):
        _apply_hunk_header(line, state)
    elif line.startswith(_FILE_META_PREFIXES):
        _apply_file_header(line, state)
    elif line.startswith("+"):
        _record_added(line, state)
    elif line.startswith("-"):
        _record_deleted(line, state)
    elif line.startswith(" "):
        _advance_context_line(state)


class ChangeAnalyzer:
    """代码变更分析器。

    用法：
        analyzer = ChangeAnalyzer(project_root="/path/to/project")
        # 方式1：直接传入 diff 文本
        changes = analyzer.parse_diff_text(diff_text)
        # 方式2：执行 git diff 获取变更
        changes = analyzer.analyze_git_diff("HEAD~1", "HEAD")
    """

    def __init__(self, project_root: str) -> None:
        if not project_root:
            raise ValueError("project_root 不能为空")
        self._project_root = project_root

    def analyze_git_diff(
        self,
        base_ref: str = "HEAD~1",
        target_ref: str = "HEAD",
        timeout: int = 10,
    ) -> list[CodeChange]:
        """执行 git diff 命令获取变更。

        边界场景：
        1. git 命令执行失败 → 返回空列表 + 告警；
        2. 超时 → 返回空列表 + 告警；
        3. 无变更 → 返回空列表。
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--unified=3", base_ref, target_ref],
                cwd=self._project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode != 0:
                logger.warning(f"git diff 失败: base={base_ref}, target={target_ref}, stderr={result.stderr.strip()}")
                return []
            return self.parse_diff_text(result.stdout)
        except subprocess.TimeoutExpired:
            logger.warning(f"git diff 超时: base={base_ref}, target={target_ref}")
            return []
        except FileNotFoundError:
            logger.warning("git 命令不存在，跳过变更分析")
            return []
        except Exception as e:
            logger.warning(f"git diff 异常: {e}")
            return []

    def parse_diff_text(self, diff_text: str) -> list[CodeChange]:
        """解析 git diff unified format 文本。

        边界场景：
        1. 空文本 → 返回空列表；
        2. 非法格式 → 跳过非法段落，返回已解析部分；
        3. 二进制文件 diff → 跳过（无行号信息）。
        """
        if not diff_text or not diff_text.strip():
            return []

        changes: list[CodeChange] = []
        state = _DiffParseState()
        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                # 文件边界：先落上一个文件，再开新状态
                _flush_diff_state(state, changes)
                state = _DiffParseState()
                continue
            _apply_diff_line(line, state)

        _flush_diff_state(state, changes)
        logger.info(f"解析 diff 完成: files={len(changes)}")
        return changes
