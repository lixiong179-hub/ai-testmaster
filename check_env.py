"""
检查环境
"""
import os

print("=== Environment ===")
print("CWD:", os.getcwd())
print("ENV FILE:", os.path.exists('.env'))
