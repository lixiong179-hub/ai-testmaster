# 测试用例管理功能 - 测试命令和常见Bug修复方案

## 一、AI生成用例测试命令

### 1. 使用curl测试AI生成测试用例

```bash
# AI生成测试用例
curl -X POST "http://localhost:8000/api/v1/case/ai-generate" \
  -H "Content-Type: application/json" \
  -d '{
    "scene": "测试用户使用错误的密码登录系统",
    "case_type": "functional"
  }'
```

### 2. 使用Postman测试

- **方法**: POST
- **URL**: `http://localhost:8000/api/v1/case/ai-generate`
- **Headers**:
  - `Content-Type: application/json`
- **Body** (raw):
  ```json
  {
    "scene": "测试用户注册功能",
    "case_type": "functional"
  }
  ```

### 3. 使用Python测试脚本

```bash
# 运行测试脚本
python test_case_management.py
```

## 二、常见Bug及修复方案

### Bug 1: DeepSeek API Key未配置

**错误信息**:
```
DeepSeek API Key未配置，请在.env文件中设置DEEPSEEK_API_KEY
```

**原因**: 
- `.env` 文件中 `DEEPSEEK_API_KEY` 未设置或设置为默认值

**修复方案**:
1. 在 `.env` 文件中配置正确的 DeepSeek API Key
2. 确保API Key格式正确，没有多余的空格或引号
3. 重启后端服务器使配置生效

```bash
# .env 文件配置示例
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
```

### Bug 2: API调用超时

**错误信息**:
```
API调用超时，请检查网络连接
```

**原因**:
- 网络连接不稳定
- DeepSeek API响应时间过长
- 超时设置过短

**修复方案**:
1. 检查网络连接，确保能访问 DeepSeek API
2. 增加超时时间（在 `app/utils/ai_client.py` 中修改 `self.timeout`）
3. 使用重试机制（已内置，最多重试3次）

```python
# 在 app/utils/ai_client.py 中修改超时时间
self.timeout = 60.0  # 从30秒增加到60秒
```

### Bug 3: API Key无效

**错误信息**:
```
DeepSeek API Key无效，请检查配置
```

**原因**:
- API Key 输入错误
- API Key 已过期或被禁用
- API Key 格式不正确

**修复方案**:
1. 检查 API Key 是否正确
2. 登录 DeepSeek 控制台重新生成 API Key
3. 确认 API Key 没有过期时间限制
4. 更新 `.env` 文件中的 API Key

### Bug 4: API调用频率超限

**错误信息**:
```
API调用频率超限，请稍后重试
```

**原因**:
- 超过了 DeepSeek API 的调用频率限制
- 短时间内发送了过多请求

**修复方案**:
1. 等待一段时间后重试（通常1-5分钟）
2. 实现请求限流（在应用层面控制调用频率）
3. 使用缓存机制，避免重复请求

```python
# 在应用层面实现简单的限流
import time

last_call_time = 0
min_interval = 2  # 最小间隔2秒

async def rate_limited_call():
    global last_call_time
    current_time = time.time()
    if current_time - last_call_time < min_interval:
        await asyncio.sleep(min_interval - (current_time - last_call_time))
    last_call_time = time.time()
    # 调用API
```

### Bug 5: Token消耗过高

**现象**:
- API 调用成功但 Token 消耗很快
- 成本超出预期

**原因**:
- 提示词过长
- 生成的测试用例过于详细
- 没有设置合理的 `max_tokens` 限制

**修复方案**:
1. 优化提示词，减少不必要的描述
2. 设置合理的 `max_tokens` 限制
3. 使用流式返回，及时停止不需要的生成

```python
# 在 app/utils/ai_client.py 中优化提示词
def _build_test_case_prompt(self, scene: str, case_type: str) -> str:
    # 精简提示词，减少Token消耗
    prompt = f"""根据场景生成测试用例：{scene}
类型：{case_type}
返回JSON格式：name, type, scene, steps, expected_result, priority, tags"""
    return prompt

# 调用时限制最大Token数
response = await self._call_api(
    messages=messages,
    max_tokens=1000  # 从2000减少到1000
)
```

### Bug 6: JSON解析失败

**错误信息**:
```
解析测试用例失败: Expecting value: line 1 column 1 (char 1)
```

**原因**:
- DeepSeek 返回的不是标准 JSON 格式
- 返回内容包含额外的文本说明
- JSON 格式错误

**修复方案**:
1. 改进提示词，要求只返回 JSON
2. 实现容错解析，从文本中提取 JSON
3. 添加格式验证和重试机制

```python
# 在 app/utils/ai_client.py 中已实现容错解析
def _extract_test_case_from_text(self, text: str, scene: str, case_type: str):
    # 从非JSON文本中提取测试用例
    # 实现了从文本中解析测试用例的逻辑
    pass
```

### Bug 7: 数据库连接错误

**错误信息**:
```
数据库操作失败: Can't connect to MySQL server
```

**原因**:
- MySQL 服务未启动
- 数据库连接配置错误
- 网络连接问题

**修复方案**:
1. 检查 MySQL 服务是否启动
2. 验证 `.env` 文件中的数据库连接信息
3. 测试数据库连接

```bash
# 测试数据库连接
mysql -h localhost -u root -p

# 检查数据库是否存在
mysql -h localhost -u root -p -e "SHOW DATABASES LIKE 'ai_testmaster';"
```

### Bug 8: 表结构不存在

**错误信息**:
```
Table 'ai_testmaster.test_cases' doesn't exist
```

**原因**:
- 数据库表未创建
- 模型未正确导入

**修复方案**:
1. 运行数据库初始化脚本
2. 确保模型正确导入到 `app/models/__init__.py`

```bash
# 初始化数据库
python init_admin.py

# 或者在代码中调用
from app.db.database import init_db
await init_db()
```

## 三、性能优化建议

### 1. Token 消耗优化

- 使用精简的提示词模板
- 限制返回的 Token 数量
- 实现结果缓存，避免重复生成

### 2. 响应速度优化

- 使用流式返回，提升用户体验
- 实现异步并发处理
- 添加请求队列，避免并发过多

### 3. 成本控制

- 监控 API 调用次数和 Token 消耗
- 设置每日/每月调用上限
- 实现预算预警机制

## 四、测试验证清单

- [ ] 配置 DeepSeek API Key
- [ ] 测试创建测试用例
- [ ] 测试获取测试用例列表
- [ ] 测试更新测试用例
- [ ] 测试删除测试用例
- [ ] 测试 AI 生成测试用例
- [ ] 测试流式生成
- [ ] 测试执行测试用例
- [ ] 验证错误处理
- [ ] 检查 Token 消耗

## 五、监控和日志

### 1. API 调用监控

```python
# 在 app/utils/ai_client.py 中添加监控
import logging

logger = logging.getLogger(__name__)

async def _call_api(self, ...):
    logger.info(f"调用DeepSeek API: scene={scene}, type={case_type}")
    # 调用API
    logger.info(f"API调用成功: tokens={response.get('usage', {}).get('total_tokens')}")
```

### 2. 错误日志记录

```python
# 在 app/api/v1/endpoints/case.py 中添加错误日志
import logging

logger = logging.getLogger(__name__)

@router.post("/ai-generate")
async def ai_generate_test_case(...):
    try:
        # 生成测试用例
        logger.info(f"AI生成测试用例成功: case_id={case.id}")
    except APIException as e:
        logger.error(f"AI生成测试用例失败: {e.message}")
        raise
```

## 六、部署注意事项

1. **环境变量配置**:
   - 生产环境必须使用真实的 DeepSeek API Key
   - 不要将 `.env` 文件提交到版本控制

2. **安全考虑**:
   - API Key 应该通过环境变量或密钥管理服务获取
   - 实现请求签名验证
   - 添加访问频率限制

3. **监控告警**:
   - 设置 Token 消耗告警阈值
   - 监控 API 调用失败率
   - 配置异常自动重试和降级策略
