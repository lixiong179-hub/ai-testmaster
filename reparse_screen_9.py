
"""
重新解析 screen 9
"""
import sys
import asyncio
from pathlib import Path

# 确保能导入模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen
from app.crud import ui_prototype as ui_prototype_crud
from app.services.ui_spec_parse_pipeline import UISpecParsePipeline
from app.core.config import settings
from loguru import logger

logger.info("开始重新解析 screen 9")

db = PrimarySessionLocal()

try:
    screen = ui_prototype_crud.get_ui_screen_by_id(db, 9)
    
    if screen:
        logger.info(f"找到屏幕: {screen.screen_name}")
        logger.info(f"原始状态: {screen.parse_status}, 错误: {screen.parse_error}")
        
        pipeline = UISpecParsePipeline(db, screen.project_id, 1, settings.UPLOAD_DIR, parse_mode="text")
        
        asyncio.run(pipeline.parse_screen(9))
        
        # 重新查询
        db.refresh(screen)
        logger.info(f"新状态: {screen.parse_status}")
        if screen.parse_status == "failed":
            logger.error(f"新错误: {screen.parse_error}")
        elif screen.parse_status == "completed":
            logger.info(f"解析成功！元素数: {screen.element_count}, 按钮数: {screen.button_count}")
    else:
        logger.error("找不到 screen 9")
        
finally:
    db.close()

