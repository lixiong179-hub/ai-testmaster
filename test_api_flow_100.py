import sys
sys.path.insert(0, '.')
import asyncio
from app.db.database import PrimarySessionLocal
from app.models.user import User
from app.models.ui_prototype import UIPrototypeScreen
from app.crud import ui_prototype as ui_prototype_crud
from app.services.ui_spec_parse_pipeline import UISpecParsePipeline
from app.api.v1.endpoints.ui_prototype.helpers import UPLOAD_DIR
from app.core.config import settings

print("=== 100% 复制 API 调用测试 ===\n")


async def test_api_flow_100():
    db = PrimarySessionLocal()

    screen_id = 12
    parse_mode = "text"
    prototype_project_id = 2

    try:
        print("=== 步骤 1: 验证用户 ===")
        current_user = db.query(User).filter(User.id == 1).first()
        print(f"  User: {current_user.id}, {current_user.username}")

        print("\n=== 步骤 2: 获取 screen ===")
        # 这是 parse_endpoints.py line 56-59
        screen = ui_prototype_crud.get_ui_screen_by_id(db, screen_id)
        print(f"  Found: {screen is not None}")
        if screen:
            print(f"    id: {screen.id}")
            print(f"    screen.project_id: {screen.project_id}")
            print(f"    prototype_project_id: {screen.prototype_project_id}")
            print(f"    parse_status: {screen.parse_status}")
            print(f"    file path: {screen.original_file_path}")

        print("\n=== 步骤 3: 检查 Project 权限 ===")
        from app.models.project import Project
        project = db.query(Project).filter(
            Project.id == screen.project_id,
            Project.user_id == current_user.id
        ).first()
        print(f"  Project exists: {project is not None}")
        if project:
            print(f"    project id: {project.id}")
            print(f"    project user_id: {project.user_id}")

        print("\n=== 步骤 4: 创建 UISpecParsePipeline ===")
        # 这是 parse_endpoints.py line 87-89
        pipeline = UISpecParsePipeline(
            db, screen.project_id, current_user.id, UPLOAD_DIR,
            parse_mode=parse_mode
        )
        print(f"  pipeline.parse_mode: {pipeline.parse_mode}")
        print(f"  pipeline.parser.parse_mode: {pipeline.parser.parse_mode}")
        print(f"  pipeline.upload_dir: {pipeline.upload_dir}")

        print("\n=== 步骤 5: 调用 batch_parse_screens ===")
        # 这是 parse_endpoints.py line 90
        result = await pipeline.batch_parse_screens([screen_id])

        print(f"\n=== 结果 ===")
        print(result)
        print(f"\nsuccess: {result['success']}, failed: {result['failed']}")

        print("\n=== 刷新 screen ===")
        db.refresh(screen)
        print(f"  parse_status: {screen.parse_status}")
        print(f"  parse_error: {screen.parse_error}")

    except Exception as e:
        print(f"\nException: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_api_flow_100())