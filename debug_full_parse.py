
"""
完整解析流程调试脚本
"""
import sys
import asyncio
from pathlib import Path

# 确保能导入模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.ui_spec_parser import UISpecParser
from loguru import logger
import base64

logger.info("开始完整解析流程调试")

async def debug_parse():
    # 初始化解析器
    parser = UISpecParser(parse_mode="text")
    
    # 测试图片路径
    test_img = Path(r"D:\PythonFile\ai-testmaster\uploads\ui_prototypes\100426\AI听写首页_20260420154655_0.jpg")
    logger.info(f"测试图片: {test_img}")
    
    try:
        # 直接调用 parse_single_screen 方法
        success, ui_spec, error = await parser.parse_single_screen(str(test_img))
        
        logger.info(f"解析成功: {success}")
        if success:
            logger.info(f"UI规格: {ui_spec}")
        else:
            logger.error(f"解析错误: {error}")
            
    except Exception as e:
        logger.error(f"解析异常: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(debug_parse())

