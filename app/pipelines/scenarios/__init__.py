"""场景流水线注册表

提供场景配置查询接口，供 API 端点和 Pipeline Runner 使用。
"""
from typing import Any, Dict, Optional

from app.pipelines.scenarios.scenario_1 import SCENARIO_1_STEPS, SCENARIO_1_NAME, SCENARIO_1_VERSION
from app.pipelines.scenarios.scenario_2 import SCENARIO_2_STEPS, SCENARIO_2_NAME, SCENARIO_2_VERSION
from app.pipelines.scenarios.scenario_3 import SCENARIO_3_STEPS, SCENARIO_3_NAME, SCENARIO_3_VERSION
from app.pipelines.scenarios.scenario_4 import SCENARIO_4_STEPS, SCENARIO_4_NAME, SCENARIO_4_VERSION
from app.pipelines.scenarios.scenario_5 import SCENARIO_5_STEPS, SCENARIO_5_NAME, SCENARIO_5_VERSION
from app.pipelines.scenarios.validation import inspect_iteration_signals, validate_scenario_inputs

_SCENARIO_REGISTRY: Dict[int, Dict[str, Any]] = {
    1: {"name": SCENARIO_1_NAME, "version": SCENARIO_1_VERSION, "steps": SCENARIO_1_STEPS},
    2: {"name": SCENARIO_2_NAME, "version": SCENARIO_2_VERSION, "steps": SCENARIO_2_STEPS},
    3: {"name": SCENARIO_3_NAME, "version": SCENARIO_3_VERSION, "steps": SCENARIO_3_STEPS},
    4: {"name": SCENARIO_4_NAME, "version": SCENARIO_4_VERSION, "steps": SCENARIO_4_STEPS},
    5: {"name": SCENARIO_5_NAME, "version": SCENARIO_5_VERSION, "steps": SCENARIO_5_STEPS},
}


def get_scenario(scenario_id: int) -> Optional[Dict[str, Any]]:
    """按场景编号获取配置。"""
    return _SCENARIO_REGISTRY.get(scenario_id)


def get_scenario_by_version(pipeline_version: str) -> Optional[Dict[str, Any]]:
    """按 pipeline_version 反查场景配置。"""
    for config in _SCENARIO_REGISTRY.values():
        if config["version"] == pipeline_version:
            return config
    return None


def list_scenarios() -> Dict[int, Dict[str, Any]]:
    """列出所有已注册场景。"""
    return dict(_SCENARIO_REGISTRY)


__all__ = [
    "get_scenario",
    "get_scenario_by_version",
    "list_scenarios",
    "inspect_iteration_signals",
    "validate_scenario_inputs",
]
