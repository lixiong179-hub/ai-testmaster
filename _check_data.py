import sys
sys.path.insert(0, ".")
from app.db.database import get_db_context
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.models.iteration import Iteration
from app.models.user import User

with get_db_context() as db:
    print("=== Users ===")
    users = db.query(User).all()
    for u in users:
        print(f"  id={u.id}, username={u.username}, is_superuser={u.is_superuser}")

    print("=== Projects ===")
    projects = db.query(Project).all()
    for p in projects:
        ptype = getattr(p, "project_type", "?")
        print(f"  id={p.id}, name={p.name}, user_id={p.user_id}, type={ptype}")

    print("=== TestPoints (first 20) ===")
    tps = db.query(TestPoint).limit(20).all()
    for t in tps:
        status = getattr(t, "status", "?")
        print(f"  id={t.id}, project_id={t.project_id}, module={t.module}, point={t.point}, status={status}")
    print(f"  Total TestPoints: {db.query(TestPoint).count()}")

    print("=== TestCases (first 10) ===")
    tcs = db.query(TestCase).limit(10).all()
    for c in tcs:
        title = (c.title or "")[:50]
        ls = getattr(c, "lifecycle_status", "?")
        print(f"  id={c.id}, project_id={c.project_id}, title={title}, generate_status={c.generate_status}, lifecycle={ls}")
    print(f"  Total TestCases: {db.query(TestCase).count()}")

    print("=== Iterations ===")
    iters = db.query(Iteration).all()
    for i in iters:
        ps = getattr(i, "pipeline_status", "?")
        print(f"  id={i.id}, project_id={i.project_id}, name={i.name}, pipeline_status={ps}")
