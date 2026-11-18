from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class RecognitionResult:
    locator_type: str
    locator_value: str
    confidence: float = 0.0
    raw_result: dict[str, Any] | None = None
    element_info: dict[str, Any] | None = None

    @property
    def is_valid(self) -> bool:
        return bool(self.locator_type and self.locator_value and self.confidence > 0)


class ElementRecognizer(ABC):
    @abstractmethod
    async def recognize(self, browser, operation_description: str, action_type: str | None = None) -> RecognitionResult:
        pass

    @abstractmethod
    async def batch_recognize(self, browser, operations: list[str]) -> list[RecognitionResult]:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        pass
