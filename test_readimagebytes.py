import sys
sys.path.insert(0, '.')
import os
from pathlib import Path
from app.services.ui_spec_parser import UISpecParser
from app.models.ui_prototype import UIPrototypeScreen
from app.db.database import PrimarySessionLocal
from app.core.config import settings

print("=== 测试 _read_image_bytes 路径检查 ===")

db = PrimarySessionLocal()
try:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == 12).first()
    if screen:
        print(f"Screen: {screen.id}")
        print(f"  path: {screen.original_file_path}")
        print()

        parser = UISpecParser()
        print("Testing _read_image_bytes...")
        image_bytes = parser._read_image_bytes(screen.original_file_path)
        print(f"  Result: {image_bytes is not None}, {len(image_bytes) if image_bytes else 0} bytes")
        print()

        if image_bytes:
            print("Testing _extract_positioned_text...")
            positioned = parser._extract_positioned_text(image_bytes)
            print(f"  Positioned text result: {positioned}")
            print(f"  Has content: {bool(positioned and len(positioned) > 0)}")
            print()

        print("=== 检查 settings ===")
        print(f"settings.UPLOAD_DIR: {settings.UPLOAD_DIR}")
        print(f"UI_PROTOTYPE_UPLOAD_DIR: {getattr(settings, 'UI_PROTOTYPE_UPLOAD_DIR', None)}")
        print()

        print("=== 检查路径 ===")
        path = Path(screen.original_file_path)
        print(f"Original path: {screen.original_file_path}")
        print(f"Resolved path: {path.resolve()}")

        allowed_dirs = [
            Path(settings.UPLOAD_DIR).resolve(),
            Path(getattr(settings, 'UI_PROTOTYPE_UPLOAD_DIR', '/tmp/ui_prototypes')).resolve(),
            Path('/tmp/ui_prototypes').resolve(),
        ]
        print(f"Allowed dirs: {[str(d) for d in allowed_dirs]}")
        is_allowed = any(str(path.resolve()).startswith(str(allowed_dir)) for allowed_dir in allowed_dirs)
        print(f"Is allowed: {is_allowed}")

finally:
    db.close()

print()
print("Done!")