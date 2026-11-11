"""K4 容器内验证脚本：创建项目+任务并调用 run 接口（容器内执行，验收后删除）。"""
import uuid

import httpx

from app.db.database import PrimarySessionLocal
from app.models.project import Project
from app.models.test_task import TaskStatus, TestTask
from app.models.user import User
from app.utils.jwt_utils import create_access_token

db = PrimarySessionLocal()
try:
    user = db.query(User).first()
    if user is None:
        raise SystemExit("NO_USER")

    suffix = uuid.uuid4().hex[:6]
    project = Project(
        name=f"k4_probe_{suffix}",
        user_id=user.id,
        description="K4 容器验证",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()

    task = TestTask(
        task_name=f"k4_task_{suffix}",
        project_id=project.id,
        case_ids=[],
        executor_id=user.id,
        status=TaskStatus.PENDING,
        total_count=0,
        progress=0,
    )
    db.add(task)
    db.commit()
    task_id = task.id
    project_id = project.id
    token = create_access_token({"sub": str(user.id)})
finally:
    db.close()

with httpx.Client(timeout=30) as client:
    resp = client.post(
        f"http://127.0.0.1:8000/api/v1/test-task/{task_id}/run",
        headers={
            "Authorization": f"Bearer {token}",
            "Origin": "http://localhost:5173",
            "Referer": "http://localhost:5173/",
        },
    )

print(f"PROJECT_ID {project_id}")
print(f"TASK_ID {task_id}")
print(f"STATUS_CODE {resp.status_code}")
print(f"BODY {resp.text[:300]}")
