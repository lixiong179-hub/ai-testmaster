"""自愈执行辅助函数 - 失败分类路由、项目ID解析与DOM快照采集。

从 SelfHealingExecuteMixin 抽离的纯函数/协程，避免 mixin 文件超 350 行。
失败分类路由为纯函数；项目ID解析与DOM快照通过显式参数注入依赖，
不持有 mixin 状态，便于独立单测。
"""
from typing import Any, Optional

from loguru import logger

from app.services.self_healing import FailureAnalysis

# DOM 快照最大保留长度，避免超大页面撑爆分析器与日志
_DOM_SNAPSHOT_MAX_LENGTH = 50000
# 允许的策略路由值
_VALID_ROUTES = frozenset({"retry", "skip", "ai_heal"})


def route_by_failure_type(analysis: FailureAnalysis) -> str:
    """根据失败分析结果路由自愈策略。

    直接采用 FailureAnalysis.suggested_strategy，未知值兜底为 ai_heal，
    确保分类器扩展新策略时不致中断主流程。

    Args:
        analysis: 失败分析结果。

    Returns:
        str: "retry" / "skip" / "ai_heal"。
    """
    strategy = analysis.suggested_strategy
    if strategy in _VALID_ROUTES:
        return strategy
    return "ai_heal"


def get_project_id_from_step(db: Any, step: Any) -> Optional[int]:
    """从步骤对象解析所属项目ID（灰度开关 Task 10.4 依赖）。

    通过 step.test_case_id 关联查询 TestCase.project_id。
    db 为 None 或查询异常时返回 None，由调用方回退全局开关。

    Args:
        db: 数据库会话，可为 None。
        step: 测试步骤对象，可为 None。

    Returns:
        Optional[int]: 项目ID，无法解析时返回 None。
    """
    if db is None or step is None:
        return None
    test_case_id = getattr(step, 'test_case_id', None)
    if not test_case_id:
        return None
    try:
        from app.models.test_case import TestCase
        case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
        return getattr(case, 'project_id', None) if case else None
    except Exception as e:
        logger.warning(f"解析项目ID失败 test_case_id={test_case_id}: {e}")
        return None


async def capture_dom_snapshot(browser: Any) -> str:
    """采集当前页面 DOM 快照，截断至 50000 字符（失败分类 Task 4.1 依赖）。

    Args:
        browser: 浏览器控制器，可为 None。

    Returns:
        str: DOM HTML 文本，异常或空时返回空字符串。
    """
    if browser is None:
        return ""
    try:
        html = await browser.execute_javascript("document.body.outerHTML")
        if not html:
            return ""
        return html[:_DOM_SNAPSHOT_MAX_LENGTH]
    except Exception as e:
        logger.warning(f"采集 DOM 快照失败: {e}")
        return ""


def is_self_healing_enabled_for_step(db: Any, step: Any) -> bool:
    """灰度开关校验（Task 10.4）: 项目级配置 AND 全局开关。

    project_id 解析失败或查询异常时回退全局开关，保证不阻断主流程。

    Args:
        db: 数据库会话，可为 None。
        step: 测试步骤对象，可为 None。

    Returns:
        bool: True 表示自愈已启用。
    """
    project_id = get_project_id_from_step(db, step)
    if project_id is not None:
        try:
            from app.services.self_healing.config_service import SelfHealingConfigService
            return SelfHealingConfigService(db).is_self_healing_enabled(project_id)
        except Exception as e:
            logger.warning(f"项目级自愈配置查询失败 project_id={project_id}: {e}")
    from app.core.config import settings
    return bool(settings.AI_SELF_HEALING_ENABLED)
