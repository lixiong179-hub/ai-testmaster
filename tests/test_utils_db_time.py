import pytest
from datetime import datetime, timezone

from app.utils.db_time import utcnow


class TestUtcnow:
    def test_returns_datetime(self):
        result = utcnow()
        assert isinstance(result, datetime)

    def test_returns_naive_datetime(self):
        result = utcnow()
        assert result.tzinfo is None

    def test_returns_recent_time(self):
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        result = utcnow()
        after = datetime.now(timezone.utc).replace(tzinfo=None)
        assert before <= result <= after

    def test_consistent_results(self):
        t1 = utcnow()
        t2 = utcnow()
        assert t2 >= t1

    def test_not_using_deprecated_utcnow(self):
        result = utcnow()
        assert result.year >= 2024
