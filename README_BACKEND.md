# AI TestMaster 后端项目

## 项目初始化

### 环境要求
- Python >= 3.10
- MySQL >= 8.0
- Redis >= 7.0

### 1. 创建虚拟环境
```bash
python -m venv venv
```

### 2. 激活虚拟环境

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置环境变量
创建 `.env` 文件：
```env
ENV=dev
SECRET_KEY=your-secret-key-here
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/ai_testmaster
REDIS_URL=redis://localhost:6379/0
```

### 5. 启动开发服务器
```bash
python app/main.py
```

或

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. 生产环境部署
```bash
gunicorn -c gunicorn.conf.py app.main:app
```

## 项目结构

```
├── app/
│   ├── api/                # 接口路由（按模块拆分）
│   │   └── v1/
│   │       └── endpoints/  # API端点
│   ├── core/               # 全局配置/异常处理/中间件
│   │   ├── config.py       # 配置文件
│   │   └── exception.py    # 异常处理
│   ├── crud/               # 数据库CRUD封装
│   ├── db/                 # 数据库连接
│   │   └── database.py     # 数据库连接管理
│   ├── models/             # SQLAlchemy数据模型
│   ├── schemas/            # Pydantic请求/响应校验
│   │   └── auth.py         # 认证相关模型
│   ├── services/           # 业务逻辑层
│   ├── tasks/              # 定时任务与自测调度
│   ├── utils/              # 工具类（加密/日志/AI调用）
│   │   └── jwt_utils.py    # JWT认证工具
│   └── main.py             # 入口文件
├── alembic/                # 数据库迁移
├── scripts/                # 运维脚本
├── tests/                  # 单元测试（pytest）
│   └── test_auth.py        # 认证模块测试
├── alembic.ini             # 数据库迁移配置
├── gunicorn.conf.py        # 生产环境部署配置
├── pytest.ini              # 测试配置
├── requirements.txt        # 依赖清单
└── README_BACKEND.md       # 项目说明
```

## 核心功能

### 1. 全局配置
- 分环境配置（dev/test/prod）
- 敏感信息加密存储
- 单例模式管理配置

### 2. 异常处理
- 统一API响应格式（code/msg/data/timestamp）
- 自定义异常类
- 全局异常捕获

### 3. 数据库连接
- 读写分离
- 连接池管理
- 自动重试机制

### 4. JWT认证
- Token生成/验证/刷新
- 密码加密（bcrypt）
- 过期时间管理

### 5. API接口
- 登录/注册
- Token刷新
- 用户信息获取
- 健康检查

## 验证步骤

### 1. 单元测试
```bash
pytest
```

### 2. 覆盖率测试
```bash
pytest --cov=app --cov-report=html
```

### 3. API测试
启动服务器后访问：
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 4. 登录测试
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin"
```

## 技术栈

- **Web框架**: FastAPI 0.104.1
- **ASGI服务器**: Uvicorn 0.24.0
- **ORM**: SQLAlchemy 2.0.23
- **数据验证**: Pydantic 2.5.0
- **认证**: python-jose + bcrypt
- **定时任务**: APScheduler 3.10.4
- **缓存**: Redis 7.0
- **数据库**: MySQL 8.0
- **测试**: pytest + pytest-cov

## 注意事项

- 开发环境设置 `ENV=dev` 启用调试模式
- 生产环境必须修改 `SECRET_KEY`
- 数据库连接URL需要根据实际情况配置
- 单元测试覆盖率要求 >= 80%
