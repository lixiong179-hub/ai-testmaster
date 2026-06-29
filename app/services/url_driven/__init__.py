"""网址驱动快速测试子包入口。

本子包按阶段逐步落地：站点探索引擎（Phase 1）、URL 自动建项（Phase 2）、
页面结构驱动用例生成（Phase 3）、一键任务编排与编排入口（Phase 4）。
"""
from app.services.url_driven.auto_case_generator import (
    AutoCaseGenerator,
    GROUNDING_SOURCE_DOM_SNAPSHOT,
)
from app.services.url_driven.auto_project_builder import (
    AutoProjectBuilder,
    SOURCE_URL_QUICK_TEST,
)
from app.services.url_driven.quick_launcher import QuickLauncher
from app.services.url_driven.site_explorer import (
    PageSnapshot,
    SiteExplorer,
    SiteMap,
)
from app.services.url_driven.task_assembler import EXECUTION_MODE_SMART, TaskAssembler

__all__ = [
    "SiteExplorer",
    "PageSnapshot",
    "SiteMap",
    "AutoProjectBuilder",
    "SOURCE_URL_QUICK_TEST",
    "AutoCaseGenerator",
    "GROUNDING_SOURCE_DOM_SNAPSHOT",
    "TaskAssembler",
    "EXECUTION_MODE_SMART",
    "QuickLauncher",
]
