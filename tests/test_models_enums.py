import pytest
from app.models.enums import LocatorStatus


class TestLocatorStatus:
    def test_pending_value(self):
        assert LocatorStatus.PENDING.value == "pending"

    def test_recorded_value(self):
        assert LocatorStatus.RECORDED.value == "recorded"

    def test_failed_value(self):
        assert LocatorStatus.FAILED.value == "failed"

    def test_all_values(self):
        values = {e.value for e in LocatorStatus}
        assert values == {"pending", "recorded", "failed"}

    def test_str_enum_behavior(self):
        assert isinstance(LocatorStatus.PENDING, str)
        assert LocatorStatus.PENDING == "pending"

    def test_from_value(self):
        assert LocatorStatus("pending") is LocatorStatus.PENDING
        assert LocatorStatus("recorded") is LocatorStatus.RECORDED
        assert LocatorStatus("failed") is LocatorStatus.FAILED

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            LocatorStatus("invalid")

    def test_member_count(self):
        assert len(LocatorStatus) == 3
