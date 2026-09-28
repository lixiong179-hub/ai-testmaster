# AI TestMaster K8s 部署指南

> Phase 1 Task 1 交付物：后端服务无状态化 + K8s 编排
> 部署目标：支持 ≥3 副本水平扩展，HPA 自动伸缩至 ≤10 副本

## 一、前置条件

| 组件 | 版本 | 用途 |
|------|------|------|
| Kubernetes | ≥1.26 | 容器编排 |
| NGINX Ingress Controller | ≥1.9 | 流量入口 |
| cert-manager | ≥1.13 | TLS 证书自动签发 |
| Prometheus Operator | ≥0.70 | 指标采集（可选） |
| kubectl | ≥1.26 | 部署工具 |
| Docker Registry | 任意 | 镜像仓库 |

## 二、镜像构建与推送

```bash
# 构建后端镜像
docker build -t registry.example.com/ai-testmaster/backend:v1.1.0 .

# 构建前端镜像（多阶段：Node 构建 → NGINX 服务）
docker build -f Dockerfile.frontend -t registry.example.com/ai-testmaster/frontend:v1.1.0 .

# 推送镜像
docker push registry.example.com/ai-testmaster/backend:v1.1.0
docker push registry.example.com/ai-testmaster/frontend:v1.1.0
```

## 三、部署步骤

### 3.1 创建命名空间与基础资源

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/secret.yaml
```

**安全提示**：部署前必须编辑 `secret.yaml`，将所有 `<PLACEHOLDER_REPLACE_ME>` 替换为真实凭据，并通过 `kubectl apply` 提交后立即从本地删除明文文件。生产环境建议使用 sealed-secrets 或 external-secrets 注入。

### 3.2 部署数据层

```bash
kubectl apply -f deploy/k8s/mysql-statefulset.yaml
kubectl apply -f deploy/k8s/redis-statefulset.yaml
kubectl apply -f deploy/k8s/minio-statefulset.yaml
```

等待数据层就绪：

```bash
kubectl -n ai-testmaster wait --for=condition=ready pod -l app.kubernetes.io/name=mysql --timeout=300s
kubectl -n ai-testmaster wait --for=condition=ready pod -l app.kubernetes.io/name=redis --timeout=60s
kubectl -n ai-testmaster wait --for=condition=ready pod -l app.kubernetes.io/name=minio --timeout=120s
```

### 3.3 配置 MySQL 主从复制

```bash
# 在从库执行复制配置（替换凭据）
kubectl -n ai-testmaster exec mysql-replica-0 -- \
    mysql -uroot -p$MYSQL_ROOT_PASSWORD -e "
    CHANGE REPLICATION SOURCE TO
        SOURCE_HOST='mysql-primary',
        SOURCE_USER='repl',
        SOURCE_PASSWORD='<REPL_PASSWORD>',
        SOURCE_LOG_FILE='mysql-bin.000001',
        SOURCE_LOG_POS=4;
    START REPLICA;
    "

# 验证复制状态
kubectl -n ai-testmaster exec mysql-replica-0 -- \
    mysql -uroot -p$MYSQL_ROOT_PASSWORD -e "SHOW REPLICA STATUS\G" | grep Running
```

### 3.4 部署应用层

```bash
kubectl apply -f deploy/k8s/backend-deployment.yaml
kubectl apply -f deploy/k8s/backend-service.yaml
kubectl apply -f deploy/k8s/frontend.yaml
kubectl apply -f deploy/k8s/hpa.yaml
kubectl apply -f deploy/k8s/ingress.yaml
```

### 3.5 部署监控（可选）

```bash
kubectl apply -f deploy/k8s/servicemonitor.yaml
```

## 四、验证部署

### 4.1 Pod 状态检查

```bash
kubectl -n ai-testmaster get pods -o wide
```

预期输出：

```
NAME                                          READY   STATUS    RESTARTS   AGE
ai-testmaster-backend-xxx-yyy                 1/1     Running   0          2m
ai-testmaster-backend-xxx-zzz                 1/1     Running   0          2m
ai-testmaster-backend-xxx-www                 1/1     Running   0          2m
ai-testmaster-frontend-xxx-yyy                1/1     Running   0          2m
ai-testmaster-frontend-xxx-zzz                1/1     Running   0          2m
mysql-primary-0                               1/1     Running   0          5m
mysql-replica-0                               1/1     Running   0          5m
redis-0                                       1/1     Running   0          5m
minio-0                                       1/1     Running   0          5m
```

### 4.2 健康检查端点验证

```bash
# Liveness 探针
kubectl -n ai-testmaster port-forward svc/ai-testmaster-backend 8000:8000
curl http://localhost:8000/live
# 预期: {"status":"alive"}

# Readiness 探针
curl http://localhost:8000/ready
# 预期: {"status":"ready","services":{"database":true,"redis":true}}

# 完整健康检查
curl http://localhost:8000/health
# 预期: {"status":"healthy","version":"1.1.0",...}
```

### 4.3 HPA 状态验证

```bash
kubectl -n ai-testmaster get hpa
```

预期输出：

```
NAME                    REFERENCE                          TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
ai-testmaster-backend   Deployment/ai-testmaster-backend   5%/70%    3         10        3          2m
```

### 4.4 水平扩展压测

```bash
# 启动负载测试（CPU 压测）
kubectl -n ai-testmaster run load-test --image=busybox --rm -it --restart=Never \
    -- /bin/sh -c "while true; do wget -q -O- http://ai-testmaster-backend:8000/api/v1/health; done"

# 监控 HPA 扩容
kubectl -n ai-testmaster get hpa -w
```

预期：CPU 利用率超 70% 后 30 秒内扩容至 4+ 副本。

## 五、回滚预案

### 5.1 应用回滚

```bash
# 查看发布历史
kubectl -n ai-testmaster rollout history deployment/ai-testmaster-backend

# 回滚到上一版本
kubectl -n ai-testmaster rollout undo deployment/ai-testmaster-backend

# 回滚到指定版本
kubectl -n ai-testmaster rollout undo deployment/ai-testmaster-backend --to-revision=2
```

### 5.2 数据回滚

- **MySQL**：通过 VolumeSnapshot 回滚 PVC
- **MinIO**：开启版本化后通过对象版本回滚

## 六、故障排查

| 现象 | 排查步骤 |
|------|----------|
| Pod CrashLoopBackOff | `kubectl logs <pod>` 查看应用日志；检查 `envFrom` 配置完整性 |
| Readiness 探针失败 | `kubectl exec <pod> -- curl localhost:8000/ready` 检查依赖连接 |
| HPA 不扩容 | `kubectl describe hpa` 查看 Metrics 状态；确认 Metrics Server 已部署 |
| 文件上传 404 | 确认 `STORAGE_BACKEND=s3` 且 MinIO Service 可达 |
| MySQL 主从延迟 | `SHOW REPLICA STATUS\G` 检查 `Seconds_Behind_Master` |

## 七、验收指标

部署完成后需通过以下验收：

| 指标 | 目标值 | 验收方法 |
|------|--------|----------|
| 后端副本数 | ≥3 | `kubectl get deployment` |
| HPA 最大副本 | 10 | `kubectl get hpa` |
| Liveness 通过率 | 100% | `kubectl get pods` 无 RESTARTS |
| Readiness 通过率 | 100% | 所有 Pod READY=1/1 |
| 水平扩展响应时间 | ≤30s | 压测触发扩容 |
| 文件上传可用 | 100% | 通过 Ingress 上传文件 |
| 数据库主从延迟 | ≤1s | `SHOW REPLICA STATUS` |
