import pytest
from unittest.mock import MagicMock
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session

from app.core.db_helper import (
    DatabaseHelper,
    TransactionHelper,
    QueryHelper,
    paginate_query,
    db_helper,
    tx_helper,
    query_helper,
)
from app.db.database import Base


class SampleModel(Base):
    __tablename__ = "test_db_helper_sample"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    status = Column(String(50))


class TestQueryHelperBuildFilterConditions:
    def test_basic_filter(self):
        conditions = QueryHelper.build_filter_conditions(
            SampleModel, id=1, name="test"
        )
        assert len(conditions) == 2

    def test_none_values_ignored(self):
        conditions = QueryHelper.build_filter_conditions(
            SampleModel, id=1, name=None, status=None
        )
        assert len(conditions) == 1

    def test_all_none_values(self):
        conditions = QueryHelper.build_filter_conditions(
            SampleModel, id=None, name=None
        )
        assert len(conditions) == 0

    def test_nonexistent_field_ignored(self):
        conditions = QueryHelper.build_filter_conditions(
            SampleModel, id=1, nonexistent_field="val"
        )
        assert len(conditions) == 1

    def test_empty_filters(self):
        conditions = QueryHelper.build_filter_conditions(SampleModel)
        assert len(conditions) == 0

    def test_mixed_valid_and_invalid(self):
        conditions = QueryHelper.build_filter_conditions(
            SampleModel, id=5, name="hello", missing="x", status=None
        )
        assert len(conditions) == 2


class TestQueryHelperBuildPagination:
    def test_first_page(self):
        offset, limit = QueryHelper.build_pagination(None, page=1, page_size=10)
        assert offset == 0
        assert limit == 10

    def test_second_page(self):
        offset, limit = QueryHelper.build_pagination(None, page=2, page_size=10)
        assert offset == 10
        assert limit == 10

    def test_custom_page_size(self):
        offset, limit = QueryHelper.build_pagination(None, page=3, page_size=20)
        assert offset == 40
        assert limit == 20

    def test_default_params(self):
        offset, limit = QueryHelper.build_pagination(None)
        assert offset == 0
        assert limit == 10

    def test_large_page_number(self):
        offset, limit = QueryHelper.build_pagination(None, page=100, page_size=50)
        assert offset == 4950
        assert limit == 50


class TestDatabaseHelperGetByIds:
    def test_empty_ids_returns_empty(self):
        result = DatabaseHelper.get_by_ids(MagicMock(), SampleModel, [])
        assert result == []

    def test_none_ids_returns_empty(self):
        result = DatabaseHelper.get_by_ids(MagicMock(), SampleModel, None)
        assert result == []


class TestDatabaseHelperDelete:
    def test_delete_success(self):
        mock_db = MagicMock()
        instance = MagicMock()
        result = DatabaseHelper.delete(mock_db, instance)
        assert result is True
        mock_db.delete.assert_called_once_with(instance)
        mock_db.commit.assert_called_once()

    def test_delete_failure(self):
        mock_db = MagicMock()
        mock_db.delete.side_effect = Exception("delete error")
        instance = MagicMock()
        result = DatabaseHelper.delete(mock_db, instance)
        assert result is False
        mock_db.rollback.assert_called_once()


class TestDatabaseHelperSafeCommit:
    def test_safe_commit_success(self):
        mock_db = MagicMock()
        result = DatabaseHelper.safe_commit(mock_db)
        assert result is True
        mock_db.commit.assert_called_once()

    def test_safe_commit_failure(self):
        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("commit error")
        result = DatabaseHelper.safe_commit(mock_db)
        assert result is False
        mock_db.rollback.assert_called_once()


class TestDatabaseHelperUpdate:
    def test_update_sets_attributes(self):
        mock_db = MagicMock()
        instance = MagicMock()
        instance.name = "old"
        instance.status = "old_status"
        result = DatabaseHelper.update(mock_db, instance, name="new", status="new_status")
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(instance)

    def test_update_ignores_nonexistent_attrs(self):
        mock_db = MagicMock()
        instance = MagicMock(spec=[])
        result = DatabaseHelper.update(mock_db, instance, nonexistent="val")
        mock_db.commit.assert_called_once()


class TestDatabaseHelperCreate:
    def test_create_instance(self):
        mock_db = MagicMock()
        result = DatabaseHelper.create(mock_db, SampleModel, name="test", status="active")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestDatabaseHelperGetAll:
    def test_get_all_default_pagination(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        result = DatabaseHelper.get_all(mock_db, SampleModel)
        assert result == []


class TestDatabaseHelperCount:
    def test_count_with_filters(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.count.return_value = 5
        result = DatabaseHelper.count(mock_db, SampleModel, name="test")
        assert result == 5

    def test_count_without_filters(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.count.return_value = 10
        result = DatabaseHelper.count(mock_db, SampleModel)
        assert result == 10


class TestTransactionHelperWithTransaction:
    def test_success(self):
        mock_db = MagicMock()
        operation = MagicMock(return_value="result")
        result = TransactionHelper.with_transaction(mock_db, operation, "arg1", key="val")
        assert result == "result"
        mock_db.commit.assert_called_once()
        operation.assert_called_once_with("arg1", key="val")

    def test_failure_rollback(self):
        mock_db = MagicMock()
        operation = MagicMock(side_effect=Exception("op error"))
        with pytest.raises(Exception, match="op error"):
            TransactionHelper.with_transaction(mock_db, operation)
        mock_db.rollback.assert_called_once()


class TestTransactionHelperSafeExecute:
    def test_success(self):
        mock_db = MagicMock()
        operation = MagicMock(return_value="result")
        success, result = TransactionHelper.safe_execute(mock_db, operation)
        assert success is True
        assert result == "result"

    def test_failure(self):
        mock_db = MagicMock()
        operation = MagicMock(side_effect=Exception("op error"))
        success, result = TransactionHelper.safe_execute(mock_db, operation)
        assert success is False
        assert "op error" in result
        mock_db.rollback.assert_called_once()


class TestPaginateQuery:
    def test_paginate(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 25
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = ["item1", "item2"]

        items, total = paginate_query(mock_db, mock_query, page=2, page_size=10)
        assert total == 25
        assert len(items) == 2

    def test_paginate_default_params(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 5
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = []

        items, total = paginate_query(mock_db, mock_query)
        assert total == 5


class TestModuleInstances:
    def test_db_helper_instance(self):
        assert isinstance(db_helper, DatabaseHelper)

    def test_tx_helper_instance(self):
        assert isinstance(tx_helper, TransactionHelper)

    def test_query_helper_instance(self):
        assert isinstance(query_helper, QueryHelper)
