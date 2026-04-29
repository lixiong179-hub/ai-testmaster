import pymysql
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

NEW_PASSWORD = "admin"

conn = pymysql.connect(
    host='localhost', user='root', password='test1234',
    database='ai_testmaster', charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)
cursor = conn.cursor()

# 1. Generate new hash
new_hash = pwd_context.hash(NEW_PASSWORD)
print(f"New hash for '{NEW_PASSWORD}': {new_hash}")

# 2. Update admin password
cursor.execute(
    "UPDATE users SET password_hash = %s WHERE username = 'admin'",
    (new_hash,)
)
conn.commit()
print(f"Updated rows: {cursor.rowcount}")

# 3. Verify the update worked
cursor.execute("SELECT password_hash FROM users WHERE username = 'admin'")
row = cursor.fetchone()
stored_hash = row['password_hash']
verify_result = pwd_context.verify(NEW_PASSWORD, stored_hash)

print()
print(f"Verification:")
print(f"  Stored hash matches '{NEW_PASSWORD}': {verify_result}")
print()

# 4. Test login via API
import requests
r = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    data={"username": "admin", "password": NEW_PASSWORD},
    timeout=10,
)
print(f"API Login Test:")
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    token = r.json().get("data", {}).get("access_token", "")
    print(f"  Token: {token[:40]}...")
    print(f"  LOGIN SUCCESS!")
else:
    print(f"  Response: {r.text[:200]}")

conn.close()
