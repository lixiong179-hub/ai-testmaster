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
from typing import List, Optional

from app.services.impact_analysis.models import CodeChange

logger = logging.getLogger(__name__)

# git diff 行范围正则：@@ -a,b +c,d @@
# 同时捕获 old 文件起始行（group 1）和 new 文件起始行（group 2），
# 以便 deleted/added 行分别使用各自文件的行号，避免连续删除行号错位。
_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


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
    ) -> List[CodeChange]:
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
                logger.warning(
                    f"git diff 失败: base={base_ref}, target={target_ref}, "
                    f"stderr={result.stderr.strip()}"
                )
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

    def parse_diff_text(self, diff_text: str) -> List[CodeChange]:
        """解析 git diff unified format 文本。

        边界场景：
        1. 空文本 → 返回空列表；
        2. 非法格式 → 跳过非法段落，返回已解析部分；
        3. 二进制文件 diff → 跳过（无行号信息）。
        """
        if not diff_text or not diff_text.strip():
            return []

        changes: List[CodeChange] = []
        current_file: Optional[str] = None
        current_added: set = set()
        current_deleted: set = set()
        is_new_file = False
        is_deleted = False
        old_line = 0  # 旧文件行号（deleted 行使用）
        new_line = 0  # 新文件行号（added 行使用）

        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                # 文件边界：保存上一个文件的变更
                if current_file is not None:
                    changes.append(self._build_change(
                        current_file, current_added, current_deleted,
                        is_new_file, is_deleted,
                    ))
                # 重置状态
                current_file = None
                current_added = set()
                current_deleted = set()
                is_new_file = False
                is_deleted = False
            elif line.startswith("new file mode"):
                is_new_file = True
            elif line.startswith("deleted file mode"):
                is_deleted = True
            elif line.startswith("+++ b/"):
                current_file = line[6:]  # 去除 "+++ b/" 前缀
            elif line.startswith("+++ /dev/null"):
                # 文件被删除，current_file 已通过 --- a/ 设置
                pass
            elif line.startswith("--- a/"):
                if current_file is None:
                    current_file = line[6:]
            elif line.startswith("@@"):
                match = _HUNK_HEADER_RE.match(line)
                if match:
                    old_line = int(match.group(1))
                    new_line = int(match.group(2))
            elif line.startswith("+") and not line.startswith("+++"):
                if current_file:
                    current_added.add(new_line)
                    new_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                if current_file:
                    current_deleted.add(old_line)
                    old_line += 1
            elif line.startswith(" "):
                if current_file:
                    old_line += 1
                    new_line += 1

        # 保存最后一个文件
        if current_file is not None:
            changes.append(self._build_change(
                current_file, current_added, current_deleted,
                is_new_file, is_deleted,
            ))

        logger.info(f"解析 diff 完成: files={len(changes)}")
        return changes

    @staticmethod
    def _build_change(
        file_path: str,
        added: set,
        deleted: set,
        is_new: bool,
        is_deleted: bool,
    ) -> CodeChange:
        """构建 CodeChange 实例。"""
        return CodeChange(
            file_path=file_path,
            added_lines=frozenset(added),
            deleted_lines=frozenset(deleted),
            is_new_file=is_new,
            is_deleted=is_deleted,
        )
