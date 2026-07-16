# AI TestMaster 前端项目

## 项目初始化

### 环境要求
- Node.js ≥ 16
- npm ≥ 8

### 安装依赖
```bash
npm install
```

### 启动开发服务器
```bash
npm run dev
```

访问地址: http://localhost:3000

### 构建生产版本
```bash
npm run build
```

### 运行代码检查
```bash
npm run lint
```

### 运行单元测试
```bash
npm run test
```

## 项目结构

```
├── public/                 # 静态资源
├── src/
│   ├── api/                # 接口封装（按模块拆分）
│   ├── assets/             # 样式/图片/图标
│   ├── components/         # 通用/业务组件
│   ├── config/             # 全局配置
│   ├── directives/         # 自定义指令（权限/防抖）
│   ├── hooks/              # 自定义Hook
│   ├── layouts/            # 布局组件
│   ├── router/             # 动态路由/权限路由
│   ├── store/              # Pinia状态管理
│   ├── styles/             # 全局样式
│   ├── types/              # 类型声明
│   ├── utils/              # 工具类（请求/加密）
│   ├── views/              # 业务页面
│   ├── App.vue             # 根组件
│   └── main.ts             # 入口文件
├── .eslintrc.js            # ESLint配置
├── .prettierrc             # Prettier配置
├── env.d.ts                # TypeScript类型声明
├── index.html              # HTML入口
├── package.json            # 项目配置
├── tsconfig.json           # TypeScript配置
├── tsconfig.node.json      # Node环境TypeScript配置
└── vite.config.ts          # Vite配置
```

## 核心功能

### 1. 登录页面
- 支持账号/手机号登录
- 验证码功能
- 密码加密
- 表单验证

### 2. 主布局
- 侧边栏导航
- 顶部导航栏
- 面包屑导航
- 用户信息下拉菜单

### 3. 仪表盘
- 系统概览统计
- 测试执行趋势图表
- 测试用例分布图表

### 4. 路由管理
- 动态路由
- 权限路由
- 路由守卫

### 5. 网络请求
- Axios拦截器
- 统一错误处理
- Token认证

## 技术栈

- **前端框架**: Vue 3.4
- **构建工具**: Vite 5.0
- **UI组件库**: Element Plus 2.8
- **状态管理**: Pinia 2.1
- **路由**: Vue Router 4.2
- **HTTP客户端**: Axios 1.6
- **图表库**: ECharts 5.4
- **TypeScript**: 5.2

## 验证步骤

1. **安装依赖**: `npm install`
2. **启动开发服务器**: `npm run dev`
3. **访问登录页面**: http://localhost:3000
4. **测试登录功能**: 输入任意账号密码，点击登录
5. **验证仪表盘**: 登录后应跳转到仪表盘页面，显示统计数据和图表
6. **运行代码检查**: `npm run lint`
7. **运行单元测试**: `npm run test`
8. **构建生产版本**: `npm run build`

## 环境变量配置

首次部署前，复制模板并填写真实配置（详见 `.env.example`）：

```bash
cp .env.example .env
```

关键配置项：

- `DATABASE_URL`：MySQL 连接串（格式 `mysql+pymysql://用户:密码@主机:3306/ai_testmaster`）
- `REDIS_URL`：Redis 连接串
- `JWT_SECRET_KEY` / `ENCRYPTION_KEY` / `ENCRYPTION_SALT`：生产环境必须使用强随机密钥（生成命令：`python -c "import secrets; print(secrets.token_urlsafe(32))"`）
- `AI_API_KEY` / `DEEPSEEK_API_KEY`：AI 模型服务密钥
- `MYSQL_ROOT_PASSWORD` / `MYSQL_PASSWORD`：Docker 部署时必填，未配置容器将拒绝启动

## Docker 部署

```bash
# 1. 准备环境变量（必填项不可留空）
cp .env.example .env

# 2. 默认部署（暴露 MySQL/Redis 端口到宿主机，适合开发/测试）
docker-compose up -d

# 3. 生产环境部署（合并 prod override，关闭 DB 端口对外映射）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. 启用监控栈（Prometheus + Grafana，可选）
docker-compose --profile monitoring up -d

# 5. 查看后端日志
docker-compose logs -f backend

# 6. 停止并清理服务
docker-compose down
```

服务端口：后端 `8000`、Nginx `80`、MySQL `3306`、Redis `6379`、Grafana `3000`、Prometheus `9090`。

## 数据库迁移（Alembic）

```bash
# 应用所有迁移到最新版本
alembic upgrade head

# 回滚一个版本
alembic downgrade -1

# 生成新的迁移脚本（修改模型后执行）
alembic revision --autogenerate -m "描述本次变更"

# 查看当前迁移版本
alembic current
```

> 注：`alembic.ini` 中 `sqlalchemy.url` 会被应用设置注入，实际运行时使用 `.env` 中的 `DATABASE_URL`。

## 后端测试

项目使用 `pytest` 进行测试，标记定义见 `pytest.ini`（默认跳过 `real_browser` 与 `real_api` 标记的测试）：

```bash
# 运行全部测试（默认排除真实浏览器/真实 API 用例）
pytest tests/ -v

# 仅运行单元测试
pytest tests/ -v -m unit

# 仅运行集成测试
pytest tests/ -v -m integration

# 运行 Pipeline 回归测试
pytest tests/regression/ -v -m regression

# 生成覆盖率报告
pytest tests/ -v --cov=app --cov-report=term-missing
```

## 注意事项

- 项目使用TypeScript严格模式，确保代码类型安全
- 遵循Airbnb Vue代码规范，使用ESLint和Prettier进行代码检查和格式化
- 所有API调用都通过Axios拦截器处理，自动添加token和错误处理
- 路由使用权限守卫，未登录用户会被重定向到登录页
