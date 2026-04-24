import sys
sys.path.insert(0, '.')
from app.core.config import settings

print(f"LOG_LEVEL: {settings.LOG_LEVEL}")
print(f"ENVIRONMENT: {settings.ENVIRONMENT}")
print(f"DEBUG: {settings.DEBUG}")

# 检查所有属性
print(f"\nAll attributes:")
for attr in dir(settings):
    if not attr.startswith('_') and 'LOG' in attr.upper():
        print(f"  {attr}: {getattr(settings, attr)}")