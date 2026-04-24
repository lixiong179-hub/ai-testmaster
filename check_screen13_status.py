"""检查screen_id=13的parse_status"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen

db = PrimarySessionLocal()
try:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == 13).first()
    
    if screen:
        logger.info(f"screen_id=13 信息:")
        logger.info(f"  名称: {screen.screen_name}")
        logger.info(f"  解析状态: {screen.parse_status}")
        logger.info(f"  解析错误: {screen.parse_error or '无'}")
        logger.info(f"  文件路径: {screen.original_file_path}")
        
        import os
        if screen.original_file_path and os.path.exists(screen.original_file_path):
            actual_size = os.path.getsize(screen.original_file_path)
            logger.info(f"  文件大小: {actual_size} bytes")
            
            if actual_size < 1024:
                logger.warning(f"  ✗ 文件过小，已损坏！")
                logger.info(f"  建议：")
                logger.info(f"    1. 删除此屏幕记录")
                logger.info(f"    2. 重新上传有效图片")
            else:
                logger.info(f"  ✓ 文件大小正常")
                
                # 重置解析状态为pending，允许重新解析
                logger.info(f"\n尝试重置解析状态为 'pending'...")
                screen.parse_status = "pending"
                screen.parse_error = None
                db.commit()
                logger.info(f"  ✓ 解析状态已重置为 'pending'")
                logger.info(f"  请重新调用解析API")
        else:
            logger.error(f"  ✗ 文件不存在")
    else:
        logger.error("screen_id=13 不存在")
        
finally:
    db.close()
