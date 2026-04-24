import sys
sys.path.insert(0, '.')
import asyncio
import traceback
from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen
from app.crud import ui_prototype as ui_prototype_crud
from app.services.ui_spec_parse_pipeline import UISpecParsePipeline
from app.api.v1.endpoints.ui_prototype.helpers import UPLOAD_DIR
from loguru import logger
import os

logger.add("debug_parse.log", level="DEBUG", backtrace=True, diagnose=True)

async def detailed_diagnosis():
    db = PrimarySessionLocal()
    try:
        screen_id = 12
        prototype_project_id = 2

        # 1. 检查 screen 是否存在
        print(f"=== 1. 查询 screen {screen_id} ===")
        screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
        if not screen:
            print(f"❌ Screen {screen_id} 不存在！")
            # 列出所有可用的 screen
            screens = db.query(UIPrototypeScreen).all()
            print(f"可用的 screens: {[s.id for s in screens]}")
            return

        print(f"✅ Screen {screen_id} 存在")
        print(f"  - screen_name: {screen.screen_name}")
        print(f"  - project_id: {screen.project_id}")
        print(f"  - original_file_path: {screen.original_file_path}")
        print(f"  - prototype_project_id: {screen.prototype_project_id}")
        print(f"  - parse_status: {screen.parse_status}")

        # 2. 检查文件是否存在
        print(f"\n=== 2. 检查文件 ===")
        file_path = screen.original_file_path
        if not file_path:
            print(f"❌ 文件路径为空！")
            return

        file_exists = os.path.exists(file_path)
        print(f"  文件存在: {file_exists}")
        if file_exists:
            print(f"  文件大小: {os.path.getsize(file_path)} bytes")

        # 3. 检查 UPLOAD_DIR 配置
        print(f"\n=== 3. 检查配置 ===")
        print(f"  helpers.UPLOAD_DIR: {UPLOAD_DIR}")

        # 4. 创建 pipeline
        print(f"\n=== 4. 创建 pipeline ===")
        pipeline = UISpecParsePipeline(
            db=db,
            project_id=screen.project_id,
            user_id=1,
            upload_dir=UPLOAD_DIR,
            parse_mode='text'
        )
        print(f"  pipeline.parse_mode: {pipeline.parse_mode}")

        # 5. 直接测试解析流程
        print(f"\n=== 5. 解析 screen {screen_id} ===")
        success, msg = await pipeline.parse_screen(screen_id)
        print(f"  结果: success={success}, msg={msg}")

        # 6. 刷新 screen 状态
        db.refresh(screen)
        print(f"  parse_status: {screen.parse_status}")
        print(f"  parse_error: {screen.parse_error}")

    except Exception as e:
        print(f"\n❌ 异常: {e}")
        print(traceback.format_exc())
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(detailed_diagnosis())