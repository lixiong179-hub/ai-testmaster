import pymysql
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

conn = pymysql.connect(
    host='localhost', user='root', password='test1234',
    database='ai_testmaster', charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)
cursor = conn.cursor()

cursor.execute("SELECT id, username, password_hash, is_active FROM users WHERE username='admin'")
user = cursor.fetchone()

if user:
    print(f"User ID:     {user['id']}")
    print(f"Username:   {user['username']}")
    print(f"Is Active:  {user['is_active']}")
    print(f"Hash (first 40): {str(user['password_hash'])[:40]}...")
    print(f"Hash (last 30):  ...{str(user['password_hash'])[-30:]}")
    print()
    
    # Test various passwords
    passwords_to_try = ["admin", "admin123", "password", "test1234", "123456"]
    for pwd in passwords_to_try:
        try:
            result = pwd_context.verify(pwd, user['password_hash'])
            print(f"  Password '{pwd}': {'MATCH!' if result else 'no match'}")
        except Exception as e:
            print(f"  Password '{pwd}': ERROR - {e}")
    
    # Also check if hash starts with correct prefix
    h = user['password_hash']
    print()
    print(f"Hash type check:")
    print(f"  Starts with $2b$ (bcrypt): {h.startswith('$2b$') or h.startswith('$2a$')}")
    print(f"  Hash length: {len(h)}")
else:
    print("Admin user NOT FOUND in database!")

# Check all users
print("\n--- All Users ---")
cursor.execute("SELECT id, username, is_active, LEFT(password_hash,20) as hash_prefix FROM users")
for row in cursor.fetchall():
    print(f"  id={row['id']}, user={row['username']}, active={row['is_active']}, hash={row['hash_prefix']}...")

conn.close()
