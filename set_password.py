import pymysql
import requests
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
NEW_PASSWORD = "password123"

conn = pymysql.connect(
    host='localhost', user='root', password='test1234',
    database='ai_testmaster', charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)
cursor = conn.cursor()

new_hash = pwd_context.hash(NEW_PASSWORD)
cursor.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (new_hash,))
conn.commit()

cursor.execute("SELECT password_hash FROM users WHERE username = 'admin'")
stored = cursor.fetchone()['password_hash']
verify = pwd_context.verify(NEW_PASSWORD, stored)

print(f"Password changed to: {NEW_PASSWORD}")
print(f"Hash verified: {verify}")

r = requests.post("http://localhost:8000/api/v1/auth/login",
                  data={"username": "admin", "password": NEW_PASSWORD}, timeout=10)
print(f"API login: {r.status_code} {'OK' if r.status_code == 200 else r.text[:100]}")

conn.close()
