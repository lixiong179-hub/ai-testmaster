"""
元素定位模型覆盖率测试
提升 element_locator.py 的测试覆盖率
"""
import sys
import os
import unittest
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.models.element_locator import ElementLocator


class TestElementLocatorStructure(unittest.TestCase):
    """测试元素定位模型结构"""
    
    def test_element_locator_import(self):
        """测试元素定位模型可以导入"""
        self.assertTrue(hasattr(ElementLocator, '__tablename__'))
        self.assertEqual(ElementLocator.__tablename__, 'element_locators')
    
    def test_element_locator_columns(self):
        """测试元素定位模型字段"""
        # 检查关键字段存在
        self.assertTrue(hasattr(ElementLocator, 'id'))
        self.assertTrue(hasattr(ElementLocator, 'step_id'))
        self.assertTrue(hasattr(ElementLocator, 'element_description'))
        self.assertTrue(hasattr(ElementLocator, 'element_type'))
        self.assertTrue(hasattr(ElementLocator, 'css_selector'))
        self.assertTrue(hasattr(ElementLocator, 'xpath'))
        self.assertTrue(hasattr(ElementLocator, 'element_id'))
        self.assertTrue(hasattr(ElementLocator, 'element_name'))
        self.assertTrue(hasattr(ElementLocator, 'ai_coordinate'))
        self.assertTrue(hasattr(ElementLocator, 'ai_confidence'))
        self.assertTrue(hasattr(ElementLocator, 'success_count'))
        self.assertTrue(hasattr(ElementLocator, 'fail_count'))
        self.assertTrue(hasattr(ElementLocator, 'source'))
        self.assertTrue(hasattr(ElementLocator, 'version'))
    
    def test_element_locator_repr(self):
        """测试元素定位模型的字符串表示"""
        # 创建一个模拟实例来测试 __repr__
        locator = ElementLocator()
        locator.id = 1
        locator.element_description = "测试按钮"
        repr_str = repr(locator)
        self.assertIn("ElementLocator", repr_str)


if __name__ == '__main__':
    unittest.main(verbosity=2)
