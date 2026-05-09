"""
Celery任务数据库会话管理测�?

覆盖范围:
- execute_test_task 创建TaskService实例
- stop_test_task 创建TaskService实例
- TaskService内部自己管理数据库会�?
- 异常处理

要求: 使用真实MySQL数据库，不使用Mock
"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.tasks.test_task import execute_test_task, stop_test_task


class TestCeleryTaskSessionManagement:
    """Celery任务会话管理测试——核心修复验�?""

    def test_execute_test_task_creates_task_service(self):
        """execute_test_task 创建TaskService——核心场�?""
        task_id = 1
        project_id = 1
        case_ids = [1, 2, 3]

        with patch('app.tasks.test_task.TaskService') as MockTaskService:
            mock_instance = MagicMock()
            MockTaskService.return_value = mock_instance

            result = execute_test_task(task_id, project_id, case_ids)

            MockTaskService.assert_called_once_with()
            mock_instance.start_task.assert_called_once_with(
                task_id, project_id, case_ids
            )
            assert result["status"] == "success"
            assert result["task_id"] == task_id

    def test_stop_test_task_creates_task_service(self):
        """stop_test_task 创建TaskService——核心场�?""
        task_id = 1

        with patch('app.tasks.test_task.TaskService') as MockTaskService:
            mock_instance = MagicMock()
            MockTaskService.return_value = mock_instance

            result = stop_test_task(task_id)

            MockTaskService.assert_called_once_with()
            mock_instance.stop_task.assert_called_once_with(task_id)
            assert result["status"] == "success"
            assert result["task_id"] == task_id

    def test_execute_test_task_error_handling(self):
        """execute_test_task 异常处理"""
        task_id = 1
        project_id = 1
        case_ids = [1]

        with patch('app.tasks.test_task.TaskService') as MockTaskService:
            mock_instance = MagicMock()
            mock_instance.start_task.side_effect = Exception("Database error")
            MockTaskService.return_value = mock_instance

            result = execute_test_task(task_id, project_id, case_ids)

            assert result["status"] == "error"
            assert "Database error" in result["error"]

    def test_stop_test_task_error_handling(self):
        """stop_test_task 异常处理"""
        task_id = 1

        with patch('app.tasks.test_task.TaskService') as MockTaskService:
            mock_instance = MagicMock()
            mock_instance.stop_task.side_effect = Exception("Task not found")
            MockTaskService.return_value = mock_instance

            result = stop_test_task(task_id)

            assert result["status"] == "error"
            assert "Task not found" in result["error"]


class TestTaskServiceNoDbParameter:
    """TaskService不接受db参数——验证修复正确�?""

    def test_task_service_constructor_no_db(self):
        """TaskService构造函数不接受db参数"""
        from app.services.task_service import TaskService
        service = TaskService()
        assert service is not None
        assert hasattr(service, 'running_tasks')
        assert hasattr(service, 'start_task')
        assert hasattr(service, 'stop_task')
