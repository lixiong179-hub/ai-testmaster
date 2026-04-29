# AI TestMaster（AI自动化测试平台）上市级技术架构设计

## 1. 整体架构

### 1.1 分层架构图

```mermaid
flowchart TD
    subgraph UserLayer[用户层]
        User[用户/测试人员]
        API[第三方系统API]
    end

    subgraph AccessLayer[接入层]
        Nginx[Nginx负载均衡]
        API_Gateway[API网关]
        Auth[认证授权服务]
    end

    subgraph ApplicationLayer[应用层]
        TestCaseService[测试用例管理服务]
        TaskService[任务调度服务]
        ReportService[报告生成服务]
        UserService[用户管理服务]
        PermissionService[权限管理服务]
    end

    subgraph AILayer[AI层]
        DeepSeekClient[DeepSeek API客户端]
        PromptEngine[提示词工程]
        TestGenerator[测试用例生成]
        FailureAnalyzer[失败分析]
    end

    subgraph AutomationLayer[自动化层]
        TestExecutor[测试执行器]
        Selenium[Selenium Web测试]
        Appium[Appium移动测试]
        Pytest[pytest测试框架]
        Allure[Allure报告]
    end

    subgraph DataLayer[数据层]
        MySQL[MySQL主从同步]
        Redis[Redis缓存]
        MinIO[MinIO对象存储]
    end

    subgraph InfrastructureLayer[基础设施层]
        Docker[Docker容器]
        K8s[Kubernetes编排]
        Prometheus[Prometheus监控]
        Grafana[Grafana可视化]
        LogService[日志服务]
    end

    User -->|访问| Nginx
    API -->|调用| API_Gateway
    Nginx -->|路由| API_Gateway
    API_Gateway -->|认证| Auth
    Auth -->|授权| ApplicationLayer
    
    TestCaseService -->|生成用例| AILayer
    TaskService -->|执行测试| AutomationLayer
    ReportService -->|分析结果| AILayer
    
    AILayer -->|调用| DeepSeekClient
    DeepSeekClient -->|返回结果| AILayer
    
    AutomationLayer -->|存储结果| DataLayer
    ApplicationLayer -->|读写数据| DataLayer
    
    DataLayer -->|监控| InfrastructureLayer
    ApplicationLayer -->|监控| InfrastructureLayer
    AutomationLayer -->|监控| InfrastructureLayer
```

### 1.2 架构设计原则

- **高可用性**：采用Nginx负载均衡、MySQL主从同步、Kubernetes编排等技术，确保系统24/7稳定运行
- **高扩展性**：服务化架构设计，支持水平扩展，应对业务增长
- **易维护性**：模块化设计，代码结构清晰，文档完善，便于维护和升级
- **安全合规**：符合ISO27001标准，实现数据加密、访问控制、操作审计等安全措施

## 2. 技术栈

| 分层 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 前端 | Vue | 3.4 | 前端框架 |
| 前端 | Vite | 5.0 | 构建工具 |
| 前端 | Element Plus | 2.8 | UI组件库 |
| 前端 | Pinia | 2.0 | 状态管理 |
| 前端 | Axios | 1.6 | HTTP客户端 |
| 后端 | Python | 3.10 | 编程语言 |
| 后端 | FastAPI | 0.104 | Web框架 |
| 后端 | Uvicorn | 0.24 | ASGI服务器 |
| 后端 | SQLAlchemy | 2.0 | ORM框架 |
| 自动化层 | Selenium | 4.15 | Web自动化测试 |
| 自动化层 | Appium | 2.5 | 移动自动化测试 |
| 自动化层 | pytest | 7.4 | 测试框架 |
| 自动化层 | Allure | 2.24 | 测试报告 |
| AI层 | DeepSeek | deepseek-chat | AI模型 |
| AI层 | LangChain | 0.1 | 提示词工程 |
| 数据层 | MySQL | 8.0 | 关系型数据库 |
| 数据层 | Redis | 7.0 | 缓存 |
| 数据层 | MinIO | - | 对象存储 |
| 基础设施 | Docker | 25.0 | 容器化 |
| 基础设施 | Nginx | 1.25 | 负载均衡 |
| 基础设施 | Prometheus | 2.45 | 监控 |
| 基础设施 | Grafana | 10.2 | 监控可视化 |

## 3. 数据库ER图

```mermaid
erDiagram
    USER ||--o{ ROLE : has
    ROLE ||--o{ PERMISSION : has
    USER ||--o{ TEST_CASE : create
    USER ||--o{ TASK : create
    TEST_CASE ||--o{ TASK : include
    TASK ||--o{ EXECUTION_RECORD : generate
    EXECUTION_RECORD ||--o{ AI_LOG : analyze

    USER {
        int id PK
        string username UK
        string password
        string email UK
        string phone
        datetime created_at
        datetime updated_at
    }

    ROLE {
        int id PK
        string name UK
        string description
        datetime created_at
        datetime updated_at
    }

    PERMISSION {
        int id PK
        string name UK
        string code UK
        string description
        datetime created_at
        datetime updated_at
    }

    TEST_CASE {
        int id PK
        string name
        string description
        string type
        string status
        string content
        int creator_id FK
        datetime created_at
        datetime updated_at
    }

    TASK {
        int id PK
        string name
        string description
        string status
        string type
        int creator_id FK
        datetime created_at
        datetime updated_at
        datetime scheduled_at
        datetime executed_at
    }

    EXECUTION_RECORD {
        int id PK
        int task_id FK
        string status
        string result
        string error_message
        datetime start_time
        datetime end_time
        float duration
    }

    AI_LOG {
        int id PK
        int execution_record_id FK
        string type
        string input
        string output
        float token_usage
        datetime created_at
    }
```

## 4. 非功能需求

### 4.1 性能
- **响应时间**：单接口响应时间≤200ms
- **并发能力**：支持100个并发测试任务
- **查询性能**：万级用例查询响应时间≤1s
- **AI处理**：测试用例生成响应时间≤5s，失败分析响应时间≤3s

### 4.2 安全
- **合规标准**：符合ISO27001信息安全管理体系标准
- **传输安全**：支持HTTPS加密传输
- **数据安全**：敏感数据脱敏存储，数据库加密
- **权限控制**：基于RBAC（基于角色的访问控制）模型
- **操作审计**：记录所有关键操作日志，支持审计追踪
- **API安全**：实现API密钥认证、请求频率限制

### 4.3 部署
- **部署模式**：支持公有云、私有化部署
- **容器化**：使用Docker容器化部署
- **编排方案**：提供Docker Compose（单机）和Kubernetes（集群）两种部署方案
- **CI/CD**：支持持续集成/持续部署
- **监控**：集成Prometheus + Grafana监控体系
- **日志**：集中式日志管理，支持日志分析和告警

### 4.4 可靠性
- **可用性**：系统可用性≥99.9%
- **容错**：实现服务降级、熔断机制
- **备份**：定期数据备份，支持灾难恢复
- **故障转移**：MySQL主从复制，支持自动故障转移

### 4.5 可维护性
- **代码规范**：遵循PEP8（Python）和ESLint（前端）代码规范
- **文档**：提供完整的API文档、部署文档、使用文档
- **日志**：详细的系统日志，便于问题定位
- **监控**：关键指标监控，及时发现和解决问题
