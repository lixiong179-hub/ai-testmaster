from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class ExecutionMode(Enum):
    AI_VISION = "ai_vision"
    API = "api"
    UNKNOWN = "unknown"


class ExecutionStrategy(Enum):
    STRICT = "strict"
    SMART = "smart"
    FAST = "fast"


@dataclass
class StrategyConfig:
    use_css_selector: bool = True
    use_xpath: bool = True
    use_ai_vision: bool = True
    max_retries: int = 1
    retry_delay: float = 1.0
    ai_timeout: int = 30
    confidence_threshold: float = 0.9
    use_locator_cache: bool = True
    cache_ttl_minutes: int = 60
    enable_batch_recognition: bool = False
    batch_size: int = 5


@dataclass
class ExecutionConfig:
    mode: ExecutionMode
    strategy: ExecutionStrategy = ExecutionStrategy.SMART
    headless: bool = True
    record_video: bool = False
    video_path: Optional[str] = None
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)

    def is_ai_vision(self) -> bool:
        return self.mode == ExecutionMode.AI_VISION

    def is_api(self) -> bool:
        return self.mode == ExecutionMode.API

    def is_strict_mode(self) -> bool:
        return self.strategy == ExecutionStrategy.STRICT

    def is_smart_mode(self) -> bool:
        return self.strategy == ExecutionStrategy.SMART

    def is_fast_mode(self) -> bool:
        return self.strategy == ExecutionStrategy.FAST
