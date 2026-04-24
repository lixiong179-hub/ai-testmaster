"""模拟API调用流程测试解析接口"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
import asyncio
from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen
from app.services.ui_spec_parse_pipeline import UISpecParsePipeline

logger.info("=" * 70)
logger.info("模拟API调用测试 - POST /api/v1/ui-prototype/parse")
logger.info("=" * 70)

db = PrimarySessionLocal()
try:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == 14).first()
    
    if not screen:
        logger.error("✗ screen_id=14 不存在")
        sys.exit(1)
    
    logger.info(f"\n[1] 查询屏幕信息:")
    logger.info(f"  ID: {screen.id}")
    logger.info(f"  名称: {screen.screen_name}")
    logger.info(f"  文件路径: {screen.original_file_path}")
    logger.info(f"  解析状态: {screen.parse_status}")
    logger.info(f"  项目ID: {screen.project_id}")
    logger.info(f"  创建者: {screen.created_by}")
    
    import os
    if screen.original_file_path and os.path.exists(screen.original_file_path):
        actual_size = os.path.getsize(screen.original_file_path)
        logger.info(f"  文件大小: {actual_size} bytes ({actual_size/1024:.2f} KB)")
    else:
        logger.error(f"  ✗ 文件不存在")
        sys.exit(1)
    
    logger.info(f"\n[2] 创建解析管道（模拟API）...")
    pipeline = UISpecParsePipeline(
        db=db,
        project_id=screen.project_id,
        user_id=screen.created_by,
        parse_mode="text"
    )
    logger.info(f"  ✓ 管道创建成功")
    logger.info(f"  parse_mode: {pipeline.parse_mode}")
    logger.info(f"  upload_dir: {pipeline.upload_dir}")
    
    logger.info(f"\n[3] 调用 batch_parse_screens([14])...")
    
    async def test_api_parse():
        result = await pipeline.batch_parse_screens([14])
        return result
    
    result = asyncio.run(test_api_parse())
    
    logger.info(f"\n[4] 解析结果:")
    logger.info(f"  total: {result.get('total')}")
    logger.info(f"  success: {result.get('success')}")
    logger.info(f"  failed: {result.get('failed')}")
    logger.info(f"  parse_mode: {result.get('parse_mode')}")
    
    results = result.get('results', [])
    for r in results:
        logger.info(f"\n  screen_id={r['screen_id']}:")
        logger.info(f"    success: {r['success']}")
        logger.info(f"    message: {r['message']}")
    
    if result.get('success', 0) == 0:
        logger.error(f"\n✗ API调用失败！")
        logger.error(f"\n对比独立脚本和API调用的差异...")
        
        logger.info(f"\n[5] 直接用parser测试相同文件...")
        from app.services.ui_spec_parser import UISpecParser
        parser = UISpecParser(parse_mode='text')
        
        async def direct_test():
            success, ui_spec, error = await parser.parse_single_screen(
                image_path=screen.original_file_path,
                screen_name_hint=screen.screen_name
            )
            return success, ui_spec, error
        
        success, ui_spec, error = asyncio.run(direct_test())
        if success:
            logger.info(f"  ✓ 直接调用成功")
            logger.info(f"  这说明问题出在API调用链路中，而非OCR本身")
        else:
            logger.error(f"  ✗ 直接调用也失败: {error}")
        
finally:
    db.close()

logger.info("\n" + "=" * 70)
