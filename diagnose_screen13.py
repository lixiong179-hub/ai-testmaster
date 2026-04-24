"""
诊断screen_id=13的解析失败问题
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
import os

logger.info("=" * 60)
logger.info("诊断 screen_id=13 解析失败")
logger.info("=" * 60)

from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen

db = PrimarySessionLocal()
try:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == 13).first()
    
    if not screen:
        logger.error("✗ screen_id=13 不存在")
        sys.exit(1)
    
    logger.info(f"\n屏幕信息:")
    logger.info(f"  ID: {screen.id}")
    logger.info(f"  名称: {screen.screen_name}")
    logger.info(f"  文件路径: {screen.original_file_path}")
    logger.info(f"  文件大小: {screen.file_size} KB")
    logger.info(f"  解析状态: {screen.parse_status}")
    logger.info(f"  解析错误: {screen.parse_error}")
    
    if screen.original_file_path:
        logger.info(f"\n文件检查:")
        if os.path.exists(screen.original_file_path):
            actual_size = os.path.getsize(screen.original_file_path)
            logger.info(f"  ✓ 文件存在")
            logger.info(f"  实际大小: {actual_size} bytes ({actual_size/1024:.2f} KB)")
            
            if actual_size < 1024:
                logger.error(f"  ✗ 文件过小，已损坏！")
                logger.info(f"  建议：删除此记录并重新上传有效图片")
                
                logger.info(f"\n文件内容预览（前20字节）:")
                with open(screen.original_file_path, 'rb') as f:
                    content = f.read(20)
                    logger.info(f"  {content.hex()}")
            else:
                logger.info(f"  ✓ 文件大小正常")
                logger.info(f"  尝试验证图片...")
                
                from app.api.v1.endpoints.ui_prototype.helpers import _validate_image_file
                is_valid, error_msg = _validate_image_file(screen.original_file_path)
                if is_valid:
                    logger.info(f"  ✓ 图片验证通过")
                else:
                    logger.error(f"  ✗ 图片验证失败: {error_msg}")
        else:
            logger.error(f"  ✗ 文件不存在")
    else:
        logger.error(f"  ✗ 文件路径为空")
        
finally:
    db.close()

logger.info("\n" + "=" * 60)
