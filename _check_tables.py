from sqlalchemy import create_engine, text
url = "mysql+pymysql://root:test1234@localhost:3306/ai_testmaster_test"
engine = create_engine(url)
with engine.connect() as conn:
    r = conn.execute(text("SHOW TABLES"))
    tables = [row[0] for row in r]
    print(f"Total tables: {len(tables)}")
    for t in sorted(tables):
        print(f"  {t}")
