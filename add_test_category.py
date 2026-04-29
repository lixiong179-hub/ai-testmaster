from app.db.database import primary_engine
from sqlalchemy import text

# Add missing column
with primary_engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE test_cases ADD COLUMN test_category VARCHAR(100) NULL COMMENT '用例分类标签'"))
        conn.commit()
        print('Added test_category column')
    except Exception as e:
        if 'Duplicate' in str(e):
            print('test_category column already exists')
        else:
            print(f'Error: {e}')
