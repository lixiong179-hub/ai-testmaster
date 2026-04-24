import sys
sys.path.insert(0, '.')
from app.db.database import PrimarySessionLocal
from app.models.ui_prototype import UIPrototypeScreen

db = PrimarySessionLocal()
screens = db.query(UIPrototypeScreen).all()
print(f"Total screens: {len(screens)}")
for s in screens:
    print(f"  id={s.id}, name={s.screen_name}, project_id={s.project_id}")
db.close()