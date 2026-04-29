# 用户与权限管理模块接口测试用例

## 1. 登录接口

### curl命令
```bash
# 登录获取token
curl -X POST "http://localhost:8000/api/v1/user/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123"
```

### Postman示例
- **方法**: POST
- **URL**: `http://localhost:8000/api/v1/user/login`
- **Headers**:
  - `Content-Type: application/x-www-form-urlencoded`
- **Body** (form-data):
  - `username`: testuser
  - `password`: password123

## 2. 获取当前用户信息

### curl命令
```bash
# 获取当前用户信息
curl -X GET "http://localhost:8000/api/v1/user/me" \
  -H "Authorization: Bearer <token>"
```

### Postman示例
- **方法**: GET
- **URL**: `http://localhost:8000/api/v1/user/me`
- **Headers**:
  - `Authorization: Bearer <token>`

## 3. 用户管理接口

### 3.1 创建用户

#### curl命令
```bash
# 创建用户
curl -X POST "http://localhost:8000/api/v1/user" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "phone": "13800138002",
    "password": "password123"
  }'
```

#### Postman示例
- **方法**: POST
- **URL**: `http://localhost:8000/api/v1/user`
- **Headers**:
  - `Authorization: Bearer <token>`
  - `Content-Type: application/json`
- **Body** (raw):
  ```json
  {
    "username": "newuser",
    "email": "newuser@example.com",
    "phone": "13800138002",
    "password": "password123"
  }
  ```

### 3.2 获取用户列表

#### curl命令
```bash
# 获取用户列表
curl -X GET "http://localhost:8000/api/v1/user?skip=0&limit=100" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: GET
- **URL**: `http://localhost:8000/api/v1/user?skip=0&limit=100`
- **Headers**:
  - `Authorization: Bearer <token>`

### 3.3 获取用户详情

#### curl命令
```bash
# 获取用户详情
curl -X GET "http://localhost:8000/api/v1/user/1" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: GET
- **URL**: `http://localhost:8000/api/v1/user/1`
- **Headers**:
  - `Authorization: Bearer <token>`

### 3.4 更新用户

#### curl命令
```bash
# 更新用户
curl -X PUT "http://localhost:8000/api/v1/user/1" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "updated@example.com",
    "phone": "13800138003"
  }'
```

#### Postman示例
- **方法**: PUT
- **URL**: `http://localhost:8000/api/v1/user/1`
- **Headers**:
  - `Authorization: Bearer <token>`
  - `Content-Type: application/json`
- **Body** (raw):
  ```json
  {
    "email": "updated@example.com",
    "phone": "13800138003"
  }
  ```

### 3.5 删除用户

#### curl命令
```bash
# 删除用户
curl -X DELETE "http://localhost:8000/api/v1/user/1" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: DELETE
- **URL**: `http://localhost:8000/api/v1/user/1`
- **Headers**:
  - `Authorization: Bearer <token>`

## 4. 角色管理接口

### 4.1 创建角色

#### curl命令
```bash
# 创建角色
curl -X POST "http://localhost:8000/api/v1/user/role" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "manager",
    "desc": "管理角色",
    "permissions": ["user:list", "user:view"]
  }'
```

#### Postman示例
- **方法**: POST
- **URL**: `http://localhost:8000/api/v1/user/role`
- **Headers**:
  - `Authorization: Bearer <token>`
  - `Content-Type: application/json`
- **Body** (raw):
  ```json
  {
    "name": "manager",
    "desc": "管理角色",
    "permissions": ["user:list", "user:view"]
  }
  ```

### 4.2 获取角色列表

#### curl命令
```bash
# 获取角色列表
curl -X GET "http://localhost:8000/api/v1/user/role?skip=0&limit=100" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: GET
- **URL**: `http://localhost:8000/api/v1/user/role?skip=0&limit=100`
- **Headers**:
  - `Authorization: Bearer <token>`

### 4.3 获取角色详情

#### curl命令
```bash
# 获取角色详情
curl -X GET "http://localhost:8000/api/v1/user/role/1" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: GET
- **URL**: `http://localhost:8000/api/v1/user/role/1`
- **Headers**:
  - `Authorization: Bearer <token>`

### 4.4 更新角色

#### curl命令
```bash
# 更新角色
curl -X PUT "http://localhost:8000/api/v1/user/role/1" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "desc": "更新后的管理角色",
    "permissions": ["user:list", "user:view", "user:update"]
  }'
```

#### Postman示例
- **方法**: PUT
- **URL**: `http://localhost:8000/api/v1/user/role/1`
- **Headers**:
  - `Authorization: Bearer <token>`
  - `Content-Type: application/json`
- **Body** (raw):
  ```json
  {
    "desc": "更新后的管理角色",
    "permissions": ["user:list", "user:view", "user:update"]
  }
  ```

### 4.5 删除角色

#### curl命令
```bash
# 删除角色
curl -X DELETE "http://localhost:8000/api/v1/user/role/1" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: DELETE
- **URL**: `http://localhost:8000/api/v1/user/role/1`
- **Headers**:
  - `Authorization: Bearer <token>`

## 5. 权限管理接口

### 5.1 创建权限

#### curl命令
```bash
# 创建权限
curl -X POST "http://localhost:8000/api/v1/user/permission" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "创建用户",
    "code": "user:create",
    "type": "api",
    "parent_id": null
  }'
```

#### Postman示例
- **方法**: POST
- **URL**: `http://localhost:8000/api/v1/user/permission`
- **Headers**:
  - `Authorization: Bearer <token>`
  - `Content-Type: application/json`
- **Body** (raw):
  ```json
  {
    "name": "创建用户",
    "code": "user:create",
    "type": "api",
    "parent_id": null
  }
  ```

### 5.2 获取权限列表

#### curl命令
```bash
# 获取权限列表
curl -X GET "http://localhost:8000/api/v1/user/permission?skip=0&limit=100" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: GET
- **URL**: `http://localhost:8000/api/v1/user/permission?skip=0&limit=100`
- **Headers**:
  - `Authorization: Bearer <token>`

### 5.3 获取权限详情

#### curl命令
```bash
# 获取权限详情
curl -X GET "http://localhost:8000/api/v1/user/permission/1" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: GET
- **URL**: `http://localhost:8000/api/v1/user/permission/1`
- **Headers**:
  - `Authorization: Bearer <token>`

### 5.4 更新权限

#### curl命令
```bash
# 更新权限
curl -X PUT "http://localhost:8000/api/v1/user/permission/1" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "创建用户权限"
  }'
```

#### Postman示例
- **方法**: PUT
- **URL**: `http://localhost:8000/api/v1/user/permission/1`
- **Headers**:
  - `Authorization: Bearer <token>`
  - `Content-Type: application/json`
- **Body** (raw):
  ```json
  {
    "name": "创建用户权限"
  }
  ```

### 5.5 删除权限

#### curl命令
```bash
# 删除权限
curl -X DELETE "http://localhost:8000/api/v1/user/permission/1" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: DELETE
- **URL**: `http://localhost:8000/api/v1/user/permission/1`
- **Headers**:
  - `Authorization: Bearer <token>`

## 6. 用户角色管理接口

### 6.1 分配角色

#### curl命令
```bash
# 分配角色
curl -X POST "http://localhost:8000/api/v1/user/role/assign?user_id=1&role_id=1" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: POST
- **URL**: `http://localhost:8000/api/v1/user/role/assign?user_id=1&role_id=1`
- **Headers**:
  - `Authorization: Bearer <token>`

### 6.2 移除角色

#### curl命令
```bash
# 移除角色
curl -X POST "http://localhost:8000/api/v1/user/role/remove?user_id=1&role_id=1" \
  -H "Authorization: Bearer <token>"
```

#### Postman示例
- **方法**: POST
- **URL**: `http://localhost:8000/api/v1/user/role/remove?user_id=1&role_id=1`
- **Headers**:
  - `Authorization: Bearer <token>`
