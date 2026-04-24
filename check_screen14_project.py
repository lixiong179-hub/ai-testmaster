"""检查screen_id=14的项目归属和API权限校验"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen, UIPrototypeProject
from app.models.project import Project
from app.crud import ui_prototype as ui_prototype_crud

db = PrimarySessionLocal()
try:
    logger.info("=" * 70)
    logger.info("检查screen_id=14的项目归属")
    logger.info("=" * 70)
    
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == 14).first()
    
    if not screen:
        logger.error("✗ screen_id=14 不存在")
        sys.exit(1)
    
    logger.info(f"\n屏幕信息:")
    logger.info(f"  ID: {screen.id}")
    logger.info(f"  名称: {screen.screen_name}")
    logger.info(f"  project_id: {screen.project_id}")
    logger.info(f"  created_by: {screen.created_by}")
    logger.info(f"  prototype_project_id: {screen.prototype_project_id}")
    
    logger.info(f"\n项目信息:")
    project = db.query(Project).filter(Project.id == screen.project_id).first()
    if project:
        logger.info(f"  项目ID: {project.id}")
        logger.info(f"  项目名称: {project.name}")
        logger.info(f"  项目user_id: {project.user_id}")
    else:
        logger.error(f"  ✗ 项目ID={screen.project_id} 不存在")
    
    logger.info(f"\n原型项目信息:")
    if screen.prototype_project_id:
        proto_project = db.query(UIPrototypeProject).filter(
            UIPrototypeProject.id == screen.prototype_project_id
        ).first()
        if proto_project:
            logger.info(f"  原型项目ID: {proto_project.id}")
            logger.info(f"  原型项目project_id: {proto_project.project_id}")
            logger.info(f"  原型项目created_by: {proto_project.created_by}")
        else:
            logger.error(f"  ✗ 原型项目ID={screen.prototype_project_id} 不存在")
    
    logger.info(f"\nAPI权限校验分析:")
    logger.info(f"  前端传入: screen_ids=[14], prototype_project_id=4, parse_mode='text'")
    logger.info(f"  API端点第62行: screen = get_ui_screen_by_id(db, 14)")
    logger.info(f"  → 不传入project_id，无项目隔离校验")
    logger.info(f"  API端点第97行: pipeline = UISpecParsePipeline(db, {screen.project_id}, 1, ...)")
    logger.info(f"  → 使用screen.project_id={screen.project_id}")
    logger.info(f"  API端点第100行: pipeline.batch_parse_screens([14])")
    logger.info(f"  → 调用 parse_screen(14)")
    logger.info(f"  parse_screen第179行: screen = get_ui_screen_by_id(db, 14, {screen.project_id})")
    logger.info(f"  → 使用project_id={screen.project_id}进行项目隔离校验")
    
    logger.info(f"\n结论:")
    if screen.project_id == 100426:
        logger.info(f"  screen.project_id={screen.project_id} 是正确的")
        logger.info(f"  权限校验应该通过")
        logger.info(f"  问题可能在其他地方...")
    else:
        logger.warning(f"  screen.project_id={screen.project_id} 可能不正确")
        logger.info(f"  需要检查上传时设置的项目ID")
    
    logger.info(f"\n[测试] 模拟API权限校验流程...")
    
    screen_by_api = ui_prototype_crud.get_ui_screen_by_id(db, 14)
    logger.info(f"  第62行查询结果: {screen_by_api.id if screen_by_api else None}")
    
    screen_by_pipeline = ui_prototype_crud.get_ui_screen_by_id(db, 14, screen.project_id)
    logger.info(f"  parse_screen查询结果: {screen_by_pipeline.id if screen_by_pipeline else None}")
    
    if screen_by_api and screen_by_pipeline:
        logger.info(f"  ✓ 两次查询都成功，权限校验没问题")
    else:
        logger.error(f"  ✗ 查询失败，权限校验有问题")

finally:
    db.close()

logger.info("\n" + "=" * 70)
