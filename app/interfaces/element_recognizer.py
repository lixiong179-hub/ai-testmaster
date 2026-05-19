from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class RecognitionResult:
    locator_type: str
    locator_value: str
    confidence: float = 0.0
    raw_result: Optional[Dict[str, Any]] = None
    element_info: Optional[Dict[str, Any]] = None

    @property
    def is_valid(self) -> bool:
        return bool(self.locator_type and self.locator_value and self.confidence > 0)


class ElementRecognizer(ABC):

    @abstractmethod
    async def recognize(self, browser, operation_description: str, action_type: Optional[str] = None) -> RecognitionResult:
        pass

    @abstractmethod
    async def batch_recognize(self, browser, operations: List[str]) -> List[RecognitionResult]:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        pass
