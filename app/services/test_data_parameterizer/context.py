
"""参数化上下文 - 维护单次执行中的参数缓存和元信息。"""
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ParameterContext:
    """参数化上下文。

    属性:
        execution_id: 执行唯一标识。
        user_id: 当前用户ID。
        project_id: 当前项目ID。
        cached_values: 已解析参数的缓存字典。
        execution_timestamp: 执行开始时间戳（固定）。
    """
    execution_id: str
    user_id: Optional[int] = None
    project_id: Optional[int] = None
    cached_values: Dict[str, str] = field(default_factory=dict)
    execution_timestamp: str = field(default="")

    def __post_init__(self) -> None:
        if not self.execution_timestamp:
            self.execution_timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
