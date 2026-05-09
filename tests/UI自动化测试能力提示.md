# AI自动化测试平台用例执行拓展自动识别UI页面功能

<br />

## **1. 概述**

本方案采用双AI引擎协同架构�?

- **Kimi K2.5（多模态模型）**：负责所有需要图像理解的任务，包括页面元素识别、跳转验证、UI对比、截图描述、智能重定位等�?
- **DeepSeek（文本模型）**：负责自然语言处理任务，包括测试目标解析、测试步骤生成、失败原因分析、报告摘要生成、语义相似度计算等�?

通过双引擎分工，既能保证视觉识别的准确性，又能利用DeepSeek的低成本和高文本理解能力，整体API成本可控�?

## **2. 系统架构（双引擎视图�?*

text

```
┌─────────────────────────────────────────────────────────────────�?
�?                       前端/报告�?                             �?
�? - 自然语言测试任务提交                                         �?
�? - 执行结果可视化（含AI分析�?                                  �?
└─────────────────────────────────────────────────────────────────�?
                                �?
                                �?
┌─────────────────────────────────────────────────────────────────�?
�?                       后端服务�?                               �?
�? - API网关 (FastAPI)                                            �?
�? - 任务调度�?(Celery)                                          �?
�? - 设备管理�?                                                  �?
�? - 基线库管�?                                                  �?
└─────────────────────────────────────────────────────────────────�?
                                �?
                                �?
┌─────────────────────────────────────────────────────────────────�?
�?                      AI 能力层（双引擎）                        �?
├───────────────────────────────┬─────────────────────────────────�?
�?  视觉引擎 (Kimi K2.5)        �?    文本引擎 (DeepSeek)         �?
�? - 页面元素识别                �?  - 自然语言测试生成            �?
�? - 跳转验证                    �?  - 测试步骤解析                �?
�? - UI变更对比                  �?  - 失败原因分析                �?
�? - 截图描述生成                �?  - 报告摘要生成                �?
�? - 智能重定�?                 �?  - 语义相似度计�?             �?
�? - 业务结果验证                �?  - 需求关键词提取              �?
└───────────────────────────────┴─────────────────────────────────�?
                                �?
                                �?
┌─────────────────────────────────────────────────────────────────�?
�?                  设备控制 & 基础设施�?                         �?
�? - Appium控制�?                                               �?
�? - PostgreSQL / Redis / RabbitMQ                               �?
└─────────────────────────────────────────────────────────────────�?
```

## **3. 核心模块详细设计**

### **3.1 AI客户端封装（新增�?*

#### **3.1.1 统一AI客户端接�?*

python

```
class VisionClient:
    """视觉模型客户端（Kimi�?""
    def __init__(self, api_key: str, redis_client):
        self.api_key = api_key
        self.redis = redis_client
        self.base_url = "https://api.moonshot.cn/v1"  # 实际地址以官方为�?

    def recognize_elements(self, screenshot: bytes, dom_hint: str = None) -> List[Dict]:
        """识别页面可交互元素，返回结构化列�?""
        # 缓存key: 截图感知哈希 + DOM结构哈希
        # 调用Kimi多模态接�?
        pass

    def validate_jump(self, before: bytes, element: Dict, after: bytes) -> Tuple[bool, str]:
        """验证跳转是否正确，返�?是否通过, 原因)"""
        pass

    def compare_ui(self, screenshot_a: bytes, screenshot_b: bytes) -> Dict:
        """对比两个版本UI差异，返回变更列�?""
        pass

    def describe_screenshot(self, screenshot: bytes) -> str:
        """生成截图的文字描述，用于辅助文本模型"""
        pass

    def locate_element_by_description(self, description: str, screenshot: bytes) -> Optional[List[int]]:
        """根据文字描述（如“页面中唯一的红色按钮”）在截图中定位元素"""
        pass


class TextClient:
    """文本模型客户端（DeepSeek�?""
    def __init__(self, api_key: str, redis_client):
        self.api_key = api_key
        self.redis = redis_client
        self.base_url = "https://api.deepseek.com/v1"

    def generate_test_from_goal(self, goal: str, app_context: str) -> List[Dict]:
        """根据自然语言目标生成测试步骤序列"""
        # 返回格式：[{"action": "click", "target": "登录按钮"}, ...]
        pass

    def analyze_failure(self, error_description: str, screenshot_desc: str, logs: str) -> str:
        """分析失败原因，给出自然语言解释"""
        pass

    def summarize_report(self, execution_data: Dict) -> str:
        """生成测试报告的自然语言摘要"""
        pass

    def extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词，用于引导遍历优先�?""
        pass
```

#### **3.1.2 缓存策略（双引擎共享�?*

- **视觉缓存**：以截图pHash + DOM哈希为key，存储元素识别结果，TTL 7天�?
- **跳转验证缓存**：以“before\_hash:clicked\_element\_desc:after\_hash”为key，存储验证结果�?
- **文本缓存**：以目标文本的MD5为key，存储生成的测试步骤，TTL 30天（因为需求描述可能重复）�?

缓存命中率目标≥90%，大幅降低API调用成本�?

### **3.2 智能遍历引擎（升级）**

原有BFS遍历基础上，引入目标驱动和AI优先级评分�?

#### **3.2.1 目标驱动的探�?*

python

```
class GoalDrivenExplorer:
    def __init__(self, device: DeviceController, vision: VisionClient, text: TextClient):
        ...

    def explore_with_goal(self, goal: str, max_pages: int = 50) -> AppGraph:
        # 1. 使用DeepSeek提取目标关键�?
        keywords = self.text.extract_keywords(goal)

        # 2. 在遍历过程中，对每个页面的元素，调用DeepSeek评分（或基于关键词简单匹配）
        # 优先点击与目标相关的元素

        # 3. 返回跳转�?
        ...
```

#### **3.2.2 动态列表处�?*

通过Kimi识别列表项模式（例如多个相同结构的卡片），自动触发滑动加载更多，直到无法滑动或达到深度限制�?

### **3.3 跳转验证与业务结果验�?*

#### **3.3.1 基础跳转验证**

使用Kimi判断点击后页面是否符合预期。如果预期是页面跳转，直接比对前后页面语义；如果预期是弹窗或状态变化，Kimi也能识别�?

#### **3.3.2 业务结果验证（新增）**

支持用户指定业务预期，例如“点击提交后显示支付成功”。验证时，先由Kimi生成后截图描述，再由DeepSeek判断是否满足业务预期�?

python

```
def validate_business_outcome(self, before: bytes, element: Dict, after: bytes, expected: str) -> Tuple[bool, str]:
    # 1. 用Kimi生成after截图的描�?
    desc = self.vision.describe_screenshot(after)
    # 2. 用DeepSeek判断描述是否符合预期
    prompt = f"截图描述：{desc}\n预期结果：{expected}\n判断是否符合预期，并给出理由�?
    return self.text.analyze(prompt)
```

### **3.4 版本迁移与智能重定位**

#### **3.4.1 重定位算法（Kimi主导�?*

当基线路径中的元素在衍生版本中找不到（基于原bound或ID）时，启用重定位�?

1. 根据基线元素的特征（类型、文本、语义）生成文本描述，如“页面底部绿色的‘确定’按钮”�?
2. 调用`vision.locate_element_by_description(description, new_screenshot)`，由Kimi在截图中定位相似元素�?
3. 如果成功，记录重定位映射，后续路径复用�?

#### **3.4.2 UI变更分析**

使用Kimi对比公版和定制版的截图，输出变更列表（元素新�?移除/移动），并评估对测试的影响�?

### **3.5 自然语言测试任务（新增API�?*

http

```
POST /api/tasks/nl
{
    "app_name": "com.example.app",
    "version": "v2.0",
    "goal": "验证用户能够使用手机号注册，并收到验证码"
}
```

后端处理流程�?

1. 调用`TextClient.generate_test_from_goal()`，将目标转为操作序列�?
2. 创建执行任务（类型为`nl_execute`），存储生成的步骤�?
3. 异步执行，每一步调用视觉引擎识别元素并执行操作，同时进行业务验证�?
4. 返回报告，包含步骤回放和AI分析�?

### **3.6 成本统计与监�?*

为控制API成本，增加成本统计模块：

- 每次调用Kimi或DeepSeek时，记录tokens数（多模态按官方计价规则）�?
- 存入数据库`api_cost_log`表，用于月度统计和报警�?
- 设置每日预算上限，超限时暂停新任务并告警�?

## **4. 数据存储设计（补充）**

新增表：

sql

```
-- API调用成本记录
CREATE TABLE api_cost_log (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(64) REFERENCES tasks(id),
    model VARCHAR(20), -- 'kimi' or 'deepseek'
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost DECIMAL(10,6),
    call_time TIMESTAMP
);

-- 自然语言测试步骤存储
CREATE TABLE nl_test_steps (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(64) REFERENCES tasks(id),
    step_index INTEGER,
    action VARCHAR(20),
    target_desc TEXT,
    status VARCHAR(20),
    screenshot_path TEXT,
    error_message TEXT
);
```

## **5. API接口完善**

### **5.1 创建自然语言测试任务**

同上�?

### **5.2 UI变更对比接口**

http

```
POST /api/compare
{
    "app_name": "com.example.app",
    "version_a": "v2.0",
    "version_b": "v2.1_custom",
    "screenshot_a": "base64_or_url",  // 可选，如果不提供则通过设备实时截图
    "screenshot_b": "base64_or_url"
}
```

返回变更列表JSON�?

## **6. 任务拆解清单（适配双引擎）**

### **史诗一：设备控制与基础能力（同原方案，略）**

### **史诗二：双引擎AI集成与缓�?*

- **特�?.1**：视觉客户端（Kimi）封�?
  - 任务2.1.1：实现多模态元素识别接�?
  - 任务2.1.2：实现跳转验证接�?
  - 任务2.1.3：实现UI对比接口
  - 任务2.1.4：实现截图描述接�?
  - 任务2.1.5：实现语义定位接�?
- **特�?.2**：文本客户端（DeepSeek）封�?
  - 任务2.2.1：实现测试步骤生成接�?
  - 任务2.2.2：实现失败分析接�?
  - 任务2.2.3：实现报告摘要生成接�?
  - 任务2.2.4：实现关键词提取接口
- **特�?.3**：统一缓存策略
  - 任务2.3.1：实现视觉缓存（感知哈希+DOM哈希�?
  - 任务2.3.2：实现文本缓存（MD5摘要�?
  - 任务2.3.3：集成Redis，统一缓存读写

### **史诗三：智能遍历与链路生成（升级�?*

- **特�?.1**：目标驱动探�?
  - 任务3.1.1：集成DeepSeek关键词提�?
  - 任务3.1.2：实现基于优先级的BFS
  - 任务3.1.3：实现动态列表处理（滑动加载更多�?
- **特�?.2**：跳转图构建（同原方案）

### **史诗四：自然语言测试执行**

- **特�?.1**：测试步骤生�?
  - 任务4.1.1：实现自然语言目标解析（调用DeepSeek�?
  - 任务4.1.2：将步骤序列转换为可执行指令
- **特�?.2**：步骤执行器
  - 任务4.2.1：实现基于语义的元素定位（调用Kimi�?
  - 任务4.2.2：实现业务结果验证（Kimi+DeepSeek�?
  - 任务4.2.3：记录步骤执行结果和截图

### **史诗五：版本迁移与智能重定位（升级）**

- **特�?.1**：智能重定位（Kimi主导�?
  - 任务5.1.1：实现元素特征提取（文本、类型、相对位置）
  - 任务5.1.2：实现基于描述的定位（Kimi�?
  - 任务5.1.3：实现多因子匹配算法（备用规则）
- **特�?.2**：UI变更对比
  - 任务5.2.1：实现截图对比接口（Kimi�?
  - 任务5.2.2：生成变更报告（DeepSeek总结�?

### **史诗六：报告与可视化（升级）**

- **特�?.1**：AI增强报告
  - 任务6.1.1：集成DeepSeek生成报告摘要
  - 任务6.1.2：对失败步骤，集成DeepSeek进行原因分析
  - 任务6.1.3：展示自然语言测试回放

### **史诗七：任务调度与API（同原方案，增加自然语言任务接口�?*

- **特�?.1**：新增自然语言任务创建接口
- **特�?.2**：新增UI对比接口

### **史诗八：成本统计与监控（新增�?*

- **特�?.1**：API调用成本统计
  - 任务8.1.1：设计成本记录表
  - 任务8.1.2：在AI客户端中埋点记录tokens和费�?
  - 任务8.1.3：实现成本报表接�?

## **7. 部署与配�?*

### **7.1 环境变量配置**

bash

```
# Kimi API
KIMI_API_KEY=sk-xxx
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.5-preview

# DeepSeek API
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-flash

# Redis, PostgreSQL, RabbitMQ等同�?
```

### **7.2 启动服务（同原方案）**

## **8. 成本估算与优�?*

### **8.1 费用模型**

- **Kimi K2.5多模�?*：按输入图像+文本 tokens 计费，约¥0.02/千tokens（假设）�?
- **DeepSeek**：�?.001/千tokens（输入），�?.002/千tokens（输出）�?

### **8.2 优化措施**

- **缓存命中率≥90%**：重复页面不再调用Kimi�?
- **页面元素识别**：使用精简prompt，只返回必要字段，减少输出tokens�?
- **跳转验证**：仅对关键路径进行验证，非核心跳转可跳过验证或使用简单规则�?
- **DeepSeek调用**：测试步骤生成只在任务开始时调用一次，报告分析只在任务结束时调用一次�?
- **设置每日预算**：超过阈值自动暂停任务，避免费用失控�?

### **8.3 预计成本（以每月100次探索任务，每次平均30个页面为例）**

- 每个页面首次识别调用Kimi：约500 tokens �?30 \* 100 \* 0.02 = 600元�?
- 跳转验证（每个页�?个跳转，首次验证）：5 \* 100 \* 0.02 = 100元�?
- 自然语言测试生成（每个任�?次DeepSeek）：100 \* 0.001 �?0.1元�?
- 报告分析（每个任�?次DeepSeek）：100 \* 0.002 �?0.2元�?
- 总计�?00�?月，若缓存命中率90%，可降至70�?月左右�?

## **9. 总结**

本方案通过Kimi+DeepSeek双引擎协同，实现了：

- **视觉理解精准**：由Kimi处理所有截图相关任务�?
- **自然语言驱动**：支持客户用业务语言描述测试目标，降低脚本维护成本�?
- **智能自愈**：UI变化时自动重定位，提升迁移成功率�?
- **成本可控**：通过缓存、精简提示、任务分离，将API费用控制在合理范围�?
- **可解释性强**：报告包含AI生成的自然语言分析，便于定位问题�?

后续可逐步引入本地轻量模型（当硬件升级后）进一步降低成本，但当前方案完全基于云API，符合低配置环境要求�?

#

