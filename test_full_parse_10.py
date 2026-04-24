"""
测试 screen_id 10 的完整解析流程
"""
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen
from app.services.ui_spec_parser import UISpecParser
from app.core.config import settings
from loguru import logger

async def main():
    logger.info("=" * 60)
    logger.info("测试 screen_id 10 的完整解析流程")
    logger.info("=" * 60)
    
    db = PrimarySessionLocal()
    
    try:
        screen = db.query(UIPrototypeScreen).filter_by(id=10).first()
        if not screen:
            logger.error("screen_id 10 不存在")
            return
        
        logger.info(f"屏幕信息: id={screen.id}, name={screen.screen_name}")
        logger.info(f"原始文件路径: {screen.original_file_path}")
        logger.info(f"当前解析状态: {screen.parse_status}")
        
        # 初始化解析器
        parser = UISpecParser(parse_mode=settings.PARSE_MODE_TEXT)
        
        # 直接调用 _parse_with_text_mode 来测试
        logger.info("\n" + "=" * 60)
        logger.info("调用 _parse_with_text_mode")
        logger.info("=" * 60)
        
        with open(screen.original_file_path, "rb") as f:
            image_bytes = f.read()
        
        success, ui_spec, msg = await parser._parse_with_text_mode(image_bytes, screen.screen_name)
        
        logger.info(f"解析结果: success={success}, msg={msg}")
        if success:
            logger.info(f"UI 规格: {ui_spec}")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
