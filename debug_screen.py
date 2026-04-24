
"""
查看屏幕信息调试脚本
"""
import sys
from pathlib import Path

# 确保能导入模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen
from loguru import logger

logger.info("查看数据库屏幕信息")

db = PrimarySessionLocal()

try:
    # 查看所有屏幕
    all_screens = db.query(UIPrototypeScreen).all()
    logger.info(f"共有 {len(all_screens)} 个屏幕")
    
    for screen in all_screens:
        logger.info(f"  ID={screen.id}, name={screen.screen_name}, path={screen.original_file_path}, status={screen.parse_status}")
        
        if screen.id == 9:
            logger.info("  -------- 屏幕 9 的详细信息 --------")
            if screen.original_file_path:
                logger.info(f"  文件是否存在: {Path(screen.original_file_path).exists()}")
            logger.info(f"  解析错误: {screen.parse_error}")
            logger.info(f"  解析模型: {screen.parse_model}")
                
finally:
    db.close()

