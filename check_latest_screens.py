"""检查最新上传的屏幕记录"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
import os
from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen

db = PrimarySessionLocal()
try:
    screens = db.query(UIPrototypeScreen).order_by(UIPrototypeScreen.id.desc()).limit(5).all()
    
    logger.info("最近的5个屏幕记录:")
    logger.info("=" * 80)
    
    for screen in screens:
        logger.info(f"\n屏幕 ID: {screen.id}")
        logger.info(f"  名称: {screen.screen_name}")
        logger.info(f"  文件路径: {screen.original_file_path}")
        logger.info(f"  数据库记录大小: {screen.file_size} KB")
        logger.info(f"  解析状态: {screen.parse_status}")
        logger.info(f"  解析错误: {screen.parse_error or '无'}")
        
        if screen.original_file_path and os.path.exists(screen.original_file_path):
            actual_size = os.path.getsize(screen.original_file_path)
            logger.info(f"  实际文件大小: {actual_size} bytes ({actual_size/1024:.2f} KB)")
            
            if actual_size < 1024:
                logger.error(f"  ✗ 文件过小，可能已损坏！")
            else:
                logger.info(f"  ✓ 文件大小正常")
                
                from app.api.v1.endpoints.ui_prototype.helpers import _validate_image_file
                is_valid, error_msg = _validate_image_file(screen.original_file_path)
                if is_valid:
                    logger.info(f"  ✓ 图片验证通过")
                else:
                    logger.error(f"  ✗ 图片验证失败: {error_msg}")
        else:
            logger.error(f"  ✗ 文件不存在")
        
        logger.info("-" * 80)
        
finally:
    db.close()
