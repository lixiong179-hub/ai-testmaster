#!/usr/bin/env python3
"""
使用 pymysql 直接连接数据库，检查用户数据
"""
import pymysql

# 数据库连接配置
host = 'localhost'
user = 'root'
password = 'Test@1234'
db_name = 'ai_testmaster'
port = 3306

try:
    # 连接数据库
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        db=db_name,
        port=port,
        charset='utf8mb4'
    )
    
    print(f"成功连接到数据库: {db_name}")
    
    # 创建游标
    cursor = conn.cursor()
    
    # 查询所有用户
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    
    print(f"数据库中共有 {len(users)} 个用户")
    for user in users:
        print(f"用户ID: {user[0]}, 用户名: {user[1]}, 邮箱: {user[3]}, 手机号: {user[4]}, 状态: {user[5]}")
    
    # 检查是否存在admin用户
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    admin_user = cursor.fetchone()
    
    if admin_user:
        print(f"\n管理员账号存在: {admin_user[1]}")
    else:
        print("\n管理员账号不存在")
        
    # 关闭游标和连接
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"错误: {str(e)}")
