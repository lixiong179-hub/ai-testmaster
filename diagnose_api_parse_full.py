"""全面诊断API解析问题"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
import os
import asyncio
from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen
from app.services.ui_spec_parse_pipeline import UISpecParsePipeline

db = PrimarySessionLocal()
try:
    logger.info("=" * 70)
    logger.info("API解析全面诊断")
    logger.info("=" * 70)
    
    logger.info("\n[1] 查找所有屏幕记录...")
    screens = db.query(UIPrototypeScreen).order_by(UIPrototypeScreen.id.desc()).limit(5).all()
    
    if not screens:
        logger.error("✗ 未找到任何屏幕记录")
        sys.exit(1)
    
    logger.info(f"找到 {len(screens)} 个最近的屏幕:")
    for screen in screens:
        logger.info(f"\n  屏幕 ID: {screen.id}")
        logger.info(f"    名称: {screen.screen_name}")
        logger.info(f"    解析状态: {screen.parse_status}")
        logger.info(f"    解析错误: {screen.parse_error or '无'}")
        logger.info(f"    文件路径: {screen.original_file_path}")
        
        if screen.original_file_path and os.path.exists(screen.original_file_path):
            actual_size = os.path.getsize(screen.original_file_path)
            logger.info(f"    文件大小: {actual_size} bytes ({actual_size/1024:.2f} KB)")
            
            if actual_size < 1024:
                logger.warning(f"    ⚠ 文件过小，可能已损坏")
            else:
                logger.info(f"    ✓ 文件大小正常")
        else:
            logger.warning(f"    ⚠ 文件不存在")
    
    pending_screens = [s for s in screens if s.parse_status == "pending"]
    failed_screens = [s for s in screens if s.parse_status == "failed"]
    
    logger.info(f"\n\n[2] 状态统计:")
    logger.info(f"  pending: {len(pending_screens)}")
    logger.info(f"  failed: {len(failed_screens)}")
    
    if failed_screens:
        logger.info(f"\n[3] 重置failed状态的屏幕为pending...")
        for screen in failed_screens:
            logger.info(f"  重置 screen_id={screen.id} ({screen.screen_name})")
            screen.parse_status = "pending"
            screen.parse_error = None
        db.commit()
        logger.info(f"  ✓ 已重置 {len(failed_screens)} 个屏幕")
        
        failed_screen_ids = [s.id for s in failed_screens]
        
        logger.info(f"\n[4] 尝试直接解析这些屏幕...")
        if failed_screen_ids:
            screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == failed_screen_ids[0]).first()
            if screen:
                logger.info(f"测试解析: {screen.screen_name}")
                logger.info(f"文件路径: {screen.original_file_path}")
                
                from app.services.ui_spec_parser import UISpecParser
                parser = UISpecParser(parse_mode='text')
                
                async def test_parse():
                    success, ui_spec, error = await parser.parse_single_screen(
                        image_path=screen.original_file_path,
                        screen_name_hint=screen.screen_name
                    )
                    if success:
                        logger.info(f"  ✓ 解析成功!")
                        logger.info(f"  screen_name: {ui_spec.get('screen_name', '未知')}")
                        logger.info(f"  elements: {len(ui_spec.get('elements', []))} 个")
                    else:
                        logger.error(f"  ✗ 解析失败: {error}")
                
                asyncio.run(test_parse())
    
    logger.info("\n" + "=" * 70)
    logger.info("诊断完成")
    logger.info("=" * 70)
    logger.info("\n建议操作:")
    logger.info("  1. 如果有failed状态的屏幕，已自动重置为pending")
    logger.info("  2. 重新调用解析API")
    logger.info("  3. 如果文件已损坏，请删除并重新上传")
        
finally:
    db.close()
