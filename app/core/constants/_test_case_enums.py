from enum import Enum, IntEnum


class TestCasePriority(IntEnum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3


def normalize_priority(value) -> int:
    if isinstance(value, int):
        return max(1, min(3, value))
    if isinstance(value, str):
        mapping = {
            "high": TestCasePriority.HIGH.value,
            "medium": TestCasePriority.MEDIUM.value,
            "low": TestCasePriority.LOW.value,
            "P0": TestCasePriority.HIGH.value,
            "P1": TestCasePriority.HIGH.value,
            "P2": TestCasePriority.MEDIUM.value,
            "P3": TestCasePriority.LOW.value,
            "1": TestCasePriority.HIGH.value,
            "2": TestCasePriority.MEDIUM.value,
            "3": TestCasePriority.LOW.value,
        }
        return mapping.get(value, TestCasePriority.MEDIUM.value)
    return TestCasePriority.MEDIUM.value


class TestCaseType(str, Enum):
    UI_AUTOMATION = "ui_automation"
    MANUAL = "manual"
    API_AUTOMATION = "api_automation"
    PERFORMANCE = "performance"
    SECURITY = "security"

    @classmethod
    def get_label(cls, value: str) -> str:
        labels = {
            cls.UI_AUTOMATION.value: "UI自动化",
            cls.MANUAL.value: "手工测试",
            cls.API_AUTOMATION.value: "API自动化",
            cls.PERFORMANCE.value: "性能测试",
            cls.SECURITY.value: "安全测试",
        }
        return labels.get(value, value)

    @classmethod
    def from_legacy(cls, value: str) -> "TestCaseType":
        legacy_map = {
            "UI": cls.UI_AUTOMATION,
            "API": cls.API_AUTOMATION,
            "接口": cls.API_AUTOMATION,
            "功能": cls.MANUAL,
            "功能测试": cls.MANUAL,
            "functional": cls.MANUAL,
            "ui_automation": cls.UI_AUTOMATION,
            "manual": cls.MANUAL,
            "api_automation": cls.API_AUTOMATION,
            "api_auto": cls.API_AUTOMATION,
            "performance": cls.PERFORMANCE,
            "security": cls.SECURITY,
            "compatibility": cls.MANUAL,
        }
        return legacy_map.get(value, cls.MANUAL)


class TestCaseGenerateStatus(IntEnum):
    GENERATING = 0
    SUCCESS = 1
    FAILED = 2


class TestCaseReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_OPTIMIZATION = "needs_optimization"


class TestCaseCorrectionStatus(str, Enum):
    FAILED_CORRECTION = "failed_correction"
    CORRECTING = "correcting"
    VERIFYING = "verifying"
    VERIFIED = "verified"


class TestCategory(str, Enum):
    UI_AUTOMATION = "ui_automation"
    MANUAL = "manual"
    API_AUTOMATION = "api_automation"
    PERFORMANCE = "performance"
    SECURITY = "security"
