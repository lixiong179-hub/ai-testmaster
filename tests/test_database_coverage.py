"""
数据库模块覆盖率测试
提升 database.py 的测试覆盖率
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock, call

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.db.database import (
    create_database_engine,
    get_db,
    get_read_db,
    get_db_context,
    get_read_db_context,
    init_db,
    drop_db,
    check_db_connection,
    Base,
    primary_engine,
    secondary_engine
)


class TestCreateDatabaseEngine(unittest.TestCase):
    """测试创建数据库引�?""
    
    @patch('app.db.database.create_engine')
    def test_create_engine_with_default_params(self, mock_create_engine):
        """测试使用默认参数创建引擎"""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        result = create_database_engine("mysql://test")
        
        self.assertEqual(result, mock_engine)
        mock_create_engine.assert_called_once()
    
    @patch('app.db.database.create_engine')
    def test_create_engine_with_custom_params(self, mock_create_engine):
        """测试使用自定义参数创建引�?""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        result = create_database_engine("mysql://test", pool_size=50, pool_timeout=60)
        
        self.assertEqual(result, mock_engine)
        mock_create_engine.assert_called_once()


class TestGetDb(unittest.TestCase):
    """测试get_db函数"""
    
    @patch('app.db.database.PrimarySessionLocal')
    def test_get_db_success(self, mock_session_local):
        """测试获取数据库会话成�?""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        # 模拟生成�?
        gen = get_db()
        session = next(gen)
        
        self.assertEqual(session, mock_session)
        mock_session.close.assert_not_called()
        
        # 触发清理
        try:
            next(gen)
        except StopIteration:
            pass
        mock_session.close.assert_called_once()
    
    @patch('app.db.database.PrimarySessionLocal')
    def test_get_db_exception(self, mock_session_local):
        """测试获取数据库会话异常处�?""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        gen = get_db()
        session = next(gen)
        
        # 模拟异常
        try:
            gen.throw(Exception("Test error"))
        except Exception:
            pass
        
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestGetReadDb(unittest.TestCase):
    """测试get_read_db函数"""
    
    @patch('app.db.database.SecondarySessionLocal')
    def test_get_read_db_success(self, mock_session_local):
        """测试获取从数据库会话成功"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        gen = get_read_db()
        session = next(gen)
        
        self.assertEqual(session, mock_session)
        mock_session.close.assert_not_called()
        
        # 触发清理
        try:
            next(gen)
        except StopIteration:
            pass
        mock_session.close.assert_called_once()


class TestGetDbContext(unittest.TestCase):
    """测试get_db_context上下文管理器"""
    
    @patch('app.db.database.PrimarySessionLocal')
    def test_get_db_context_success(self, mock_session_local):
        """测试上下文管理器成功执行"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        with get_db_context() as db:
            self.assertEqual(db, mock_session)
        
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
    
    @patch('app.db.database.PrimarySessionLocal')
    def test_get_db_context_exception(self, mock_session_local):
        """测试上下文管理器异常处理"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        with self.assertRaises(Exception):
            with get_db_context() as db:
                raise Exception("Test error")
        
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestGetReadDbContext(unittest.TestCase):
    """测试get_read_db_context上下文管理器"""
    
    @patch('app.db.database.SecondarySessionLocal')
    def test_get_read_db_context_success(self, mock_session_local):
        """测试从库上下文管理器成功执行"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        with get_read_db_context() as db:
            self.assertEqual(db, mock_session)
        
        mock_session.close.assert_called_once()
    
    @patch('app.db.database.SecondarySessionLocal')
    def test_get_read_db_context_exception(self, mock_session_local):
        """测试从库上下文管理器异常处理"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        with self.assertRaises(Exception):
            with get_read_db_context() as db:
                raise Exception("Test error")
        
        mock_session.close.assert_called_once()


class TestInitDb(unittest.TestCase):
    """测试init_db函数"""
    
    @patch('app.db.database.Base')
    @patch('app.db.database.primary_engine')
    def test_init_db(self, mock_engine, mock_base):
        """测试初始化数据库"""
        init_db()
        
        mock_base.metadata.create_all.assert_called_once_with(bind=mock_engine)


class TestDropDb(unittest.TestCase):
    """测试drop_db函数"""
    
    @patch('app.db.database.Base')
    @patch('app.db.database.primary_engine')
    def test_drop_db(self, mock_engine, mock_base):
        """测试删除数据库表"""
        drop_db()
        
        mock_base.metadata.drop_all.assert_called_once_with(bind=mock_engine)


class TestCheckDbConnection(unittest.TestCase):
    """测试check_db_connection函数"""
    
    @patch('app.db.database.primary_engine')
    def test_check_connection_success(self, mock_engine):
        """测试连接检查成�?""
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        result = check_db_connection()
        
        self.assertTrue(result)
        mock_conn.execute.assert_called_once()
    
    @patch('app.db.database.primary_engine')
    def test_check_connection_failure(self, mock_engine):
        """测试连接检查失�?""
        mock_engine.connect.side_effect = Exception("Connection failed")
        
        result = check_db_connection()
        
        self.assertFalse(result)


class TestBase(unittest.TestCase):
    """测试Base�?""
    
    def test_base_exists(self):
        """测试Base存在"""
        self.assertIsNotNone(Base)


class TestEngines(unittest.TestCase):
    """测试引擎实例"""
    
    def test_primary_engine_exists(self):
        """测试主引擎存�?""
        self.assertIsNotNone(primary_engine)
    
    def test_secondary_engine_exists(self):
        """测试从引擎存�?""
        self.assertIsNotNone(secondary_engine)


if __name__ == '__main__':
    unittest.main(verbosity=2)
