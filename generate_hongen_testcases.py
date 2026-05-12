"""
洪恩早教机项目(ID=3) 完整测试用例生成脚本
============================================
基于真实业务流程和需求文档生成测试用例

覆盖流程：
1. 用户登录认证流程
2. 项目管理流程
3. 需求文档上传和解析流程
4. 测试点提取和管理流程
5. AI生成测试用例流程
6. 测试用例审核流程
7. 测试任务创建和执行流程
8. 测试报告生成流程
9. 前端页面展示和交互流程（链接管理/设备清单/个人中心/预装应用）
"""
import pymysql
import json
from datetime import datetime

# 数据库连接配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'test1234',
    'database': 'ai_testmaster',
    'charset': 'utf8mb4'
}

PROJECT_ID = 3
PROJECT_NAME = "洪恩早教机"
TEST_ENV_URL = "https://admin-jxw-panda-test.ihumand.com/"
TEST_ACCOUNT = "admin123"


def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def generate_test_cases():
    """生成完整的测试用例集合"""

    # 定义测试用例数据 - 覆盖全部业务流程
    test_cases_data = [
        # ==================== 1. 用户登录认证流程 (5个用例) ====================
        {
            "module": "用户认证",
            "title": "使用正确账号密码登录系统",
            "precondition": f"1. 系统服务已启动且可访问\n2. 已注册用户账号: {TEST_ACCOUNT}\n3. 用户账号状态正常(未禁用)",
            "steps_json": [
                {"step": 1, "action": "打开系统登录页面", "expected_result": "成功显示登录页面，包含用户名输入框、密码输入框、登录按钮"},
                {"step": 2, "action": f"在用户名输入框中输入: {TEST_ACCOUNT}", "expected_result": "用户名正常显示在输入框中"},
                {"step": 3, "action": f"在密码输入框中输入正确的密码", "expected_result": "密码以密文形式显示"},
                {"step": 4, "action": "点击登录按钮", "expected_result": "登录请求发送成功，返回access_token、refresh_token、token_type、expires_in字段"}
            ],
            "expected_result": "1. 登录成功，HTTP状态码200\n2. 返回有效的JWT access_token\n3. token有效期1800秒(30分钟)\n4. 同时返回refresh_token用于刷新",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "用户认证",
            "title": "使用错误密码登录系统-验证错误提示",
            "precondition": f"1. 系统服务已启动\n2. 已存在用户账号: {TEST_ACCOUNT}",
            "steps_json": [
                {"step": 1, "action": "打开系统登录页面", "expected_result": "成功显示登录页面"},
                {"step": 2, "action": f"输入正确的用户名: {TEST_ACCOUNT}", "expected_result": "用户名输入成功"},
                {"step": 3, "action": "输入错误的密码(如: wrongpassword)", "expected_result": "密码输入成功"},
                {"step": 4, "action": "点击登录按钮", "expected_result": "登录请求被拒绝"}
            ],
            "expected_result": "1. 登录失败，HTTP状态码401 Unauthorized\n2. 返回错误信息: \"用户名或密码错误\"\n3. 响应头包含WWW-Authenticate: Bearer字段\n4. 不返回任何token信息",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "用户认证",
            "title": "使用不存在的用户名登录系统",
            "precondition": "1. 系统服务已启动\n2. 数据库中不存在该用户名",
            "steps_json": [
                {"step": 1, "action": "打开系统登录页面", "expected_result": "成功显示登录页面"},
                {"step": 2, "action": "输入不存在的用户名(如: nonexistent_user)", "expected_result": "用户名输入成功"},
                {"step": 3, "action": "输入任意密码", "expected_result": "密码输入成功"},
                {"step": 4, "action": "点击登录按钮", "expected_result": "登录请求被拒绝"}
            ],
            "expected_result": "1. 登录失败，HTTP状态码401 Unauthorized\n2. 返回错误信息: \"用户名或密码错误\"(不暴露用户不存在的信息，防止枚举攻击)",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "用户认证",
            "title": "使用已禁用的账号登录系统",
            "precondition": "1. 系统服务已启动\n2. 存在已被管理员禁用的用户账号(is_active=False)",
            "steps_json": [
                {"step": 1, "action": "打开系统登录页面", "expected_result": "成功显示登录页面"},
                {"step": 2, "action": "输入已禁用用户的用户名", "expected_result": "用户名输入成功"},
                {"step": 3, "action": "输入正确的密码", "expected_result": "密码输入成功"},
                {"step": 4, "action": "点击登录按钮", "expected_result": "登录请求被拒绝"}
            ],
            "expected_result": "1. 登录失败，HTTP状态码401 Unauthorized\n2. 返回错误信息: \"用户已被禁用\"\n3. 提示用户联系管理员恢复账号",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "用户认证",
            "title": "获取当前登录用户信息",
            "precondition": "1. 已成功登录系统并获取有效access_token\n2. Token未过期",
            "steps_json": [
                {"step": 1, "action": "构造GET请求到 /api/v1/auth/me 接口", "expected_result": "请求构建成功"},
                {"step": 2, "action": "在Authorization头中添加Bearer token", "expected_result": "Token格式正确: Bearer <access_token>"},
                {"step": 3, "action": "发送请求获取用户信息", "expected_result": "请求处理成功"}
            ],
            "expected_result": "1. HTTP状态码200\n2. 返回用户ID、用户名、邮箱、是否激活、创建时间、角色列表\n3. 数据与数据库中的用户记录一致",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },

        # ==================== 2. 项目管理流程 (6个用例) ====================
        {
            "module": "项目管理",
            "title": "查看洪恩早教机项目详情",
            "precondition": f"1. 已登录系统并获得有效token\n2. 项目(ID={PROJECT_ID})已存在于系统中\n3. 当前用户为项目所有者",
            "steps_json": [
                {"step": 1, "action": f"构造GET请求到 /api/v1/project/{PROJECT_ID}", "expected_result": "请求URL正确"},
                {"step": 2, "action": "添加Authorization头(Bearer token)", "expected_result": "认证信息添加成功"},
                {"step": 3, "action": "发送GET请求获取项目详情", "expected_result": "服务器接收请求"}
            ],
            "expected_result": f"""1. HTTP状态码200，返回项目完整信息:
   - id: {PROJECT_ID}
   - name: 洪恩早教机
   - project_type: web
   - status: 1(正常)
   - create_time/update_time时间戳
2. 返回关联的文件列表(files)
3. 返回Web环境配置(web_env_configs)，包含测试环境URL、账号密码(解密后)
4. 设备配置(device_config)根据实际情况返回""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "项目管理",
            "title": "获取项目列表-验证分页功能",
            "precondition": "1. 已登录系统\n2. 当前用户下至少存在一个项目",
            "steps_json": [
                {"step": 1, "action": "构造GET请求到 /api/v1/project/list?page=1&page_size=10", "expected_result": "请求参数正确"},
                {"step": 2, "action": "添加Authorization头", "expected_result": "认证通过"},
                {"step": 3, "action": "发送请求获取项目列表", "expected_result": "请求成功"}
            ],
            "expected_result": """1. HTTP状态码200
2. 返回数据结构包含:
   - items: 项目列表数组(每项含id/name/description/project_type/status/create_time)
   - total: 总数
   - page: 当前页码=1
   - page_size: 每页数量=10
3. 仅返回当前用户拥有的项目(权限隔离)
4. 分页计算正确: offset=(page-1)*page_size""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "项目管理",
            "title": "获取项目Web环境配置信息",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})已配置Web环境",
            "steps_json": [
                {"step": 1, "action": f"构造GET请求到 /api/v1/project/{PROJECT_ID}/config", "expected_result": "请求URL正确"},
                {"step": 2, "action": "添加Authorization头", "expected_result": "认证通过"},
                {"step": 3, "action": "发送请求获取配置", "expected_result": "请求成功"}
            ],
            "expected_result": f"""1. HTTP状态码200
2. 返回配置信息:
   - project_type: web
   - web_env_configs: 包含test/staging/prod三个环境配置
     * test环境: url={TEST_ENV_URL}, username={TEST_ACCOUNT}, password(已解密)
     * staging/prod环境可能为空
   - device_config: null或具体配置
3. 密码字段已解密(非gAAAAA开头的加密格式)""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "项目管理",
            "title": "更新项目Web环境配置-测试环境",
            "precondition": f"1. 已登录系统\n2. 为项目所有者\n3. 项目(ID={PROJECT_ID})存在",
            "steps_json": [
                {"step": 1, "action": f"构造PUT请求到 /api/v1/project/{PROJECT_ID}/config", "expected_result": "请求URL正确"},
                {"step": 2, "action": "请求体包含web_env_configs.test配置(url/username/password)", "expected_result": "JSON格式正确"},
                {"step": 3, "action": "添加Authorization头并发送请求", "expected_result": "认证通过，请求发送成功"}
            ],
            "expected_result": """1. HTTP状态码200
2. 配置更新成功，返回更新后的完整配置
3. 密码自动加密存储(gAAAAA开头)
4. 返回的密码是解密后的明文
5. 项目update_time更新为当前时间""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "项目管理",
            "title": "无权限用户访问项目-验证403错误",
            "precondition": "1. 已登录系统(用户A)\n2. 存在属于其他用户B的项目",
            "steps_json": [
                {"step": 1, "action": "使用用户A的token访问用户B的项目详情接口", "expected_result": "请求发送成功"},
                {"step": 2, "action": "服务器验证项目归属权", "expected_result": "权限检查执行"}
            ],
            "expected_result": """1. HTTP状态码403 Forbidden
2. 返回错误信息: "无权限操作此项目"
3. 不泄露项目的任何详细信息(安全性)""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "项目管理",
            "title": "获取被测对象信息(兼容旧接口)",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})已配置测试环境",
            "steps_json": [
                {"step": 1, "action": f"构造GET请求到 /api/v1/project/{PROJECT_ID}/test-object", "expected_result": "请求URL正确"},
                {"step": 2, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"}
            ],
            "expected_result": f"""1. HTTP状态码200
2. 返回被测对象信息:
   - type: web
   - url: {TEST_ENV_URL}
   - username: {TEST_ACCOUNT}
   - password: 解密后的密码
   - device_info: {{}}或null
3. 数据从web_env_configs.test中提取""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },

        # ==================== 3. 需求文档上传和解析流程 (5个用例) ====================
        {
            "module": "文件管理",
            "title": "上传需求文档(docx格式)-洪恩迭代需求文档",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})存在且有权访问\n3. 准备好需求文档文件(洪恩迭代需求文档.docx)",
            "steps_json": [
                {"step": 1, "action": "构造POST multipart/form-data请求到 /api/v1/file/upload", "expected_result": "请求类型正确"},
                {"step": 2, "action": "添加表单字段: project_id=3, file=文件对象, resource_type=requirement", "expected_result": "表单字段完整"},
                {"step": 3, "action": "添加Authorization头并发送上传请求", "expected_result": "认证通过"},
                {"step": 4, "action": "等待文件上传完成", "expected_result": "服务器接收并保存文件"}
            ],
            "expected_result": """1. HTTP状态码200
2. 文件上传成功，返回文件信息:
   - file_name: 洪恩迭代需求文档.docx
   - file_type: docx
   - resource_type: requirement(或自动识别)
   - size: 文件大小(KB)
   - extract_status: pending(待提取)
   - upload_time: 上传时间戳
3. 文件物理存储在 uploads/3/ 目录下
4. 数据库project_files表中新增记录""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "文件管理",
            "title": "查询项目文件列表-验证文件展示",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})下已有上传的文件",
            "steps_json": [
                {"step": 1, "action": f"构造GET请求到 /api/v1/file/list/{PROJECT_ID}", "expected_result": "请求URL正确"},
                {"step": 2, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"}
            ],
            "expected_result": """1. HTTP状态码200
2. 返回文件列表:
   - items: 文件数组，按upload_time降序排列
   - total: 文件总数
3. 每个文件包含完整信息(id/file_name/file_type/resource_type/size/extract_status等)
4. 仅返回is_active=True的文件(软删除过滤)
5. 验证洪恩迭代需求文档.docx在列表中""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "文件管理",
            "title": "提取需求文档内容-异步处理",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})下存在待提取的文件(extract_status=pending或completed)\n3. 文件ID已知(如ID=19)",
            "steps_json": [
                {"step": 1, "action": "构造POST请求到 /api/v1/file/extract-content", "expected_result": "请求URL正确"},
                {"step": 2, "action": "请求体: {project_id: 3, file_ids: [19], force_refresh: false}", "expected_result": "JSON格式正确"},
                {"step": 3, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"},
                {"step": 4, "action": "等待异步提取任务完成", "expected_result": "后台任务执行"}
            ],
            "expected_result": """1. HTTP状态码200
2. 返回: "提取任务已启动"
3. 后台异步处理:
   - 读取docx文件内容
   - 解析文本内容
   - 更新project_files表的content字段
   - extract_status更新为completed
   - extracted_at记录提取时间
4. 若文件已提取(force_refresh=false)，跳过重复提取
5. 若force_refresh=true，强制重新提取""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "文件管理",
            "title": "更新文件资源类型和描述",
            "precondition": f"1. 已登录系统\n2. 项目下存在文件记录(ID=19)",
            "steps_json": [
                {"step": 1, "action": "构造PUT请求到 /api/v1/file/19", "expected_result": "请求URL正确"},
                {"step": 2, "action": "请求体: {resource_type: 'requirement', description: '洪恩早教机迭代版本需求文档'}", "expected_result": "JSON格式正确"},
                {"step": 3, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"}
            ],
            "expected_result": """1. HTTP状态码200
2. 文件信息更新成功:
   - resource_type更新为requirement
   - description更新成功
3. 返回更新后的完整文件信息
4. update_time更新为当前时间""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "文件管理",
            "title": "删除项目文件-软删除验证",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})下存在可删除的文件",
            "steps_json": [
                {"step": 1, "action": "构造DELETE请求到 /api/v1/file/{{file_id}}?project_id=3", "expected_result": "请求URL正确"},
                {"step": 2, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"}
            ],
            "expected_result": """1. HTTP状态码200
2. 返回: "删除成功"
3. 执行软删除: is_active设置为False
4. 物理文件保留不删除(可恢复)
5. 再次查询文件列表时，该文件不再显示
6. 若文件不属于该项目或不存在，返回404错误""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },

        # ==================== 4. 测试点提取和管理流程 (4个用例) ====================
        {
            "module": "测试点管理",
            "title": "查看产品线管理模块的全部测试点",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})下已导入12个产品线管理模块测试点(ID:217-228)",
            "steps_json": [
                {"step": 1, "action": "查询test_points表: SELECT * FROM test_points WHERE project_id=3 ORDER BY id", "expected_result": "SQL执行成功"},
                {"step": 2, "action": "遍历结果集统计测试点数量", "expected_result": "共12个测试点"},
                {"step": 3, "action": "验证每个测试点的字段完整性(module/function/point/priority)", "expected_result": "字段值不为空"}
            ],
            "expected_result": """1. 成功返回12个测试点记录
2. 所有测试点的module字段均为"产品线管理"
3. 功能分布:
   - 创建产品线(表单展示): ID217
   - 创建产品线-字段校验(名称/描述/计数器): ID218-ID220
   - 创建产品线-创建流程(提交/清空/刷新/提示): ID221-ID224
   - 创建产品线-异常处理(重名): ID225
   - 创建产品线-取消功能(清空/不影响列表): ID226-ID227
   - 创建产品线-非功能(交互流畅性): ID228
4. 优先级分布: 高(1)=8个, 中(2)=3个, 低(3)=1个""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "测试点管理",
            "title": "验证测试点与项目的关联关系",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})和测试点数据已就绪",
            "steps_json": [
                {"step": 1, "action": "查询项目是否存在: SELECT * FROM projects WHERE id=3", "expected_result": "项目存在"},
                {"step": 2, "action": "查询测试点: SELECT COUNT(*) FROM test_points WHERE project_id=3", "expected_result": "返回数量>0"},
                {"step": 3, "action": "验证外键约束: project_id必须指向有效项目", "expected_result": "引用完整性正确"}
            ],
            "expected_result": """1. 所有测试点的project_id=3，指向洪恩早教机项目
2. 删除项目时，级联删除关联的测试点(ondelete=CASCADE)
3. 无法创建指向不存在项目的测试点(外键约束)
4. 多项目隔离: 不同项目的测试点互不可见""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "测试点管理",
            "title": "测试点优先级分类统计",
            "precondition": f"1. 项目(ID={PROJECT_ID})下有12个测试点",
            "steps_json": [
                {"step": 1, "action": "按优先级分组统计: SELECT priority, COUNT(*) FROM test_points WHERE project_id=3 GROUP BY priority", "expected_result": "SQL执行成功"},
                {"step": 2, "action": "分析各优先级的测试点占比", "expected_result": "统计完成"}
            ],
            "expected_result": """1. 优先级1(高): 8个测试点 - 核心业务逻辑和必现场景
   - 表单展示、必填校验、创建流程、异常处理
2. 优先级2(中): 3个测试点 - 重要但非核心的功能
   - 字符计数器、取消功能、交互流畅性
3. 优先级3(低): 1个测试点 - 可选的增强体验
   - 成功提示消息
4. 优先级分配合理，符合测试策略""",
            "priority": 3,
            "case_type": "API",
            "test_category": "manual"
        },
        {
            "module": "测试点管理",
            "title": "新增测试点到项目中",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})存在",
            "steps_json": [
                {"step": 1, "action": "构造POST请求创建新测试点", "expected_result": "请求构建成功"},
                {"step": 2, "action": "请求体: {project_id:3, module:'链接管理', function:'添加人字段', point:'验证新增链接时添加人字段自动填充', priority:1}", "expected_result": "JSON格式正确"},
                {"step": 3, "action": "发送请求并验证响应", "expected_result": "测试点创建成功"}
            ],
            "expected_result": """1. 测试点创建成功，返回新记录ID
2. 数据库test_points表新增一条记录
3. 字段完整性: module/function/point/priority/create_time均有值
4. project_id=3确保归属正确
5. 新测试点可在列表中查询到""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },

        # ==================== 5. AI生成测试用例流程 (5个用例) ====================
        {
            "module": "AI用例生成",
            "title": "调用AI生成单个测试用例-基础模式",
            "precondition": f"""1. 已登录系统并获得有效token
2. DeepSeek API Key已配置(.env文件)
3. 项目(ID={PROJECT_ID})存在
4. 描述文本长度>=10字符""",
            "steps_json": [
                {"step": 1, "action": "构造POST请求到 /api/v1/test-case/ai-generate", "expected_result": "请求URL正确"},
                {"step": 2, "action": "请求体: {project_id: 3, description: '验证产品线名称为空时点击创建按钮，前端弹出提示请输入产品线名称'}", "expected_result": "JSON格式正确，描述>=10字符"},
                {"step": 3, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"},
                {"step": 4, "action": "等待AI模型处理并返回结果", "expected_result": "DeepSeek API调用成功"}
            ],
            "expected_result": """1. HTTP状态码200
2. 测试用例生成成功并保存到数据库:
   - case_no: CASE3-YYYYMMDDHHMMSS格式
   - module: AI生成
   - case_type: UI
   - generate_status: 1(成功)
3. 返回用例详情(id/title/precondition/steps/expected_result/priority)
4. 同时创建TestStep记录(步骤明细)
5. AI生成的步骤符合测试点要求""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "AI用例生成",
            "title": "AI增强模式生成测试用例-结合需求文档上下文",
            "precondition": f"""1. 已登录系统
2. DeepSeek API可用
3. 项目(ID={PROJECT_ID})
4. 需求文档(ID=19)已提取内容
5. 测试点已定义""",
            "steps_json": [
                {"step": 1, "action": "构造POST请求到 /api/v1/test-case/ai-enhanced-generate", "expected_result": "请求URL正确"},
                {"step": 2, "action": "请求体包含:", "expected_result": "参数完整"},
                {"step": 3, "action": "  - project_id: 3", "expected_result": ""},
                {"step": 4, "action": "  - description: '链接管理模块-添加人字段功能测试'", "expected_result": ""},
                {"step": 5, "action": "  - case_type: functional", "expected_result": ""},
                {"step": 6, "action": "  - enhanced_mode: true", "expected_result": ""},
                {"step": 7, "action": "  - context: {requirement_content: '...', test_point: {...}}", "expected_result": "上下文数据准备完毕"},
                {"step": 8, "action": "发送请求并等待增强生成结果", "expected_result": "AI处理完成"}
            ],
            "expected_result": """1. HTTP状态码200
2. 使用generate_test_case_enhanced函数(增强模式)
3. 生成的用例包含更详细的测试数据(test_data字段)
4. 步骤包含具体的操作参数和预期结果
5. 用例质量高于基础模式(更贴近实际业务场景)
6. 返回完整的用例结构(含test_data)""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "AI用例生成",
            "title": "批量生成测试用例-流式SSE响应",
            "precondition": f"""1. 已登录系统
2. DeepSeek API可用
3. 项目(ID={PROJECT_ID})有多个测试点(12个)
4. 需求文档已就绪""",
            "steps_json": [
                {"step": 1, "action": "构造POST请求到 /api/v1/test-case/batch-generate/stream", "expected_result": "请求URL正确"},
                {"step": 2, "action": "请求体: {project_id: 3, test_point_ids: [217,218,219,...], requirement_file_ids: [19]}", "expected_result": "指定要生成的测试点和需求文档"},
                {"step": 3, "action": "添加Authorization头", "expected_result": "认证通过"},
                {"step": 4, "action": "发送请求并监听SSE流式响应", "expected_result": "Content-Type: text/event-stream"}
            ],
            "expected_result": """1. 返回StreamingResponse，媒体类型text/event-stream
2. SSE事件流格式: data: {json}\\n\\n
3. 进度事件包含:
   - progress: 0-100生成进度百分比
   - message: 当前处理状态(如"正在生成第3/12个测试点...")
   - status: processing/completed/error
4. 每个测试点生成完成后立即推送
5. 最终事件: data: [DONE]\\n\\n
6. 所有测试用例保存到test_cases表""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "AI用例生成",
            "title": "获取AI生成的上下文信息-需求+UI+测试点",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})有文件和测试点数据",
            "steps_json": [
                {"step": 1, "action": "构造POST请求到 /api/v1/test-case/generate-context", "expected_result": "请求URL正确"},
                {"step": 2, "action": "请求体: {project_id: 3, requirement_file_ids: [19], test_point_ids: [217,218], force_refresh: false}", "expected_result": "参数完整"},
                {"step": 3, "action": "发送请求获取上下文", "expected_result": "请求成功"}
            ],
            "expected_result": """1. HTTP状态码200
2. 返回上下文数据:
   - requirement_content: 需求文档提取的文本内容
   - requirement_length: 内容长度(字符数)
   - ui_descriptions: UI原型图描述数组(如有)
   - ui_count: UI图数量
   - test_points: 测试点列表(含id/module/function/point/priority)
   - test_point_count: 测试点数量
   - files_used: 使用的文件ID列表
   - warnings: 警告信息(如某文件提取失败)
3. 数据用于后续AI生成时的prompt构建""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "AI用例生成",
            "title": "AI服务异常处理-API Key无效",
            "precondition": "1. 已登录系统\n2. .env文件中DEEPSEEK_API_KEY配置错误或为空",
            "steps_json": [
                {"step": 1, "action": "构造POST请求到 /api/v1/test-case/ai-generate", "expected_result": "请求构建成功"},
                {"step": 2, "action": "请求体: {project_id: 3, description: '测试描述文本'}", "expected_result": "参数正确"},
                {"step": 3, "action": "发送请求触发AI生成", "expected_result": "调用DeepSeek API"}
            ],
            "expected_result": """1. HTTP状态码503 Service Unavailable
2. 返回错误信息: "AI服务认证失败: {具体错误}。请检查.env文件中的DEEPSEEK_API_KEY是否正确。"
3. 触发AIAuthenticationError异常
4. 数据库事务回滚，不产生脏数据
5. 日志记录详细错误信息便于排查""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },

        # ==================== 6. 测试用例审核流程 (4个用例) ====================
        {
            "module": "用例审核",
            "title": "查看待审核的测试用例列表",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})下有AI生成的测试用例(review_status=pending)\n3. 已有用例ID: 271-274",
            "steps_json": [
                {"step": 1, "action": f"构造GET请求到 /api/v1/test-case?project_id={PROJECT_ID}&page=1&page_size=10", "expected_result": "请求URL正确"},
                {"step": 2, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"},
                {"step": 3, "action": "筛选review_status=pending的用例", "expected_result": "筛选完成"}
            ],
            "expected_result": """1. HTTP状态码200
2. 返回测试用例列表，包含ID 271-274的用例
3. 每个用例显示审核状态: pending
4. 用例信息完整: case_no/module/title/priority/case_type/review_status
5. 支持分页浏览""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "用例审核",
            "title": "审核通过测试用例-更新状态为approved",
            "precondition": f"1. 已登录系统(审核人角色)\n2. 存在待审核的测试用例(ID=271)",
            "steps_json": [
                {"step": 1, "action": "构造PUT请求到 /api/v1/test-case/271", "expected_result": "请求URL正确"},
                {"step": 2, "action": "请求体: {review_status: 'approved', review_comment: '用例设计合理，步骤清晰', reviewed_by: 'admin'}", "expected_result": "JSON格式正确"},
                {"step": 3, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"}
            ],
            "expected_result": """1. HTTP状态码200
2. 测试用例审核状态更新:
   - review_status: approved
   - review_comment: "用例设计合理，步骤清晰"
   - reviewed_by: admin(审核人用户名)
   - reviewed_at: 审核时间戳
3. 用例可用于后续测试任务执行""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "用例审核",
            "title": "驳回测试用例-更新状态为rejected并填写原因",
            "precondition": f"1. 已登录系统(审核人角色)\n2. 存在待审核的测试用例(ID=272)",
            "steps_json": [
                {"step": 1, "action": "构造PUT请求到 /api/v1/test-case/272", "expected_result": "请求URL正确"},
                {"step": 2, "action": "请求体: {review_status: 'rejected', review_comment: '前置条件不够详细，需补充测试环境准备步骤', reviewed_by: 'admin'}", "expected_result": "驳回原因明确"},
                {"step": 3, "action": "发送请求完成驳回操作", "expected_result": "状态更新成功"}
            ],
            "expected_result": """1. HTTP状态码200
2. 审核状态更新为rejected
3. 记录驳回原因: "前置条件不够详细，需补充测试环境准备步骤"
4. 记录审核人和审核时间
5. 该用例不能被选入测试任务执行
6. 开发者可根据驳回意见修改用例后重新提交审核""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "用例审核",
            "title": "标记用例需要优化-needs_optimization状态",
            "precondition": f"1. 已登录系统\n2. 存在待审核用例(ID=273)",
            "steps_json": [
                {"step": 1, "action": "构造PUT请求更新用例273", "expected_result": "请求构建成功"},
                {"step": 2, "action": "设置review_status='needs_optimization'", "expected_result": "状态值正确"},
                {"step": 3, "action": "填写优化建议: '建议增加异常场景的测试步骤'", "expected_result": "建议内容合理"},
                {"step": 4, "action": "提交更新请求", "expected_result": "更新成功"}
            ],
            "expected_result": """1. HTTP状态码200
2. 审核状态: needs_optimization
3. 记录优化建议供开发者参考
4. 用例处于中间状态，既不是完全通过也不是完全驳回
5. 支持后续重新审核流程""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },

        # ==================== 7. 测试任务创建和执行流程 (5个用例) ====================
        {
            "module": "测试任务",
            "title": "创建测试任务-关联多个测试用例",
            "precondition": f"""1. 已登录系统
2. 项目(ID={PROJECT_ID})存在
3. 已有审核通过的测试用例(至少1个)
4. 准备好用例ID列表""",
            "steps_json": [
                {"step": 1, "action": "构造POST请求到 /api/v1/test_task", "expected_result": "请求URL正确"},
                {"step": 2, "action": "请求体: {project_id: 3, task_name: '洪恩早教机产品线模块回归测试', description: '覆盖产品线管理模块的核心测试场景', case_ids: [271,272,273]}", "expected_result": "JSON格式正确"},
                {"step": 3, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"},
                {"step": 4, "action": "验证任务创建结果", "expected_result": "任务和测试结果记录创建成功"}
            ],
            "expected_result": """1. HTTP状态码200
2. 测试任务创建成功:
   - task_id: 新任务ID
   - task_name: 洪恩早教机产品线模块回归测试
   - project_id: 3
   - status: 0(等待执行)
   - total_count: 3(关联的用例数)
   - create_time: 创建时间
3. test_tasks表新增记录
4. test_results表批量插入3条记录(每个用例一条)
   - exec_status: 0(未执行)
   - 关联task_id和case_id""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "测试任务",
            "title": "查询测试任务列表-按项目筛选",
            "precondition": f"1. 已登录系统\n2. 项目(ID={PROJECT_ID})下存在测试任务(ID=17)",
            "steps_json": [
                {"step": 1, "action": "构造GET请求到 /api/v1/test_task?project_id=3&page=1&page_size=10", "expected_result": "请求URL正确"},
                {"step": 2, "action": "发送请求获取任务列表", "expected_result": "请求成功"}
            ],
            "expected_result": """1. HTTP状态码200
2. 返回任务列表:
   - total: 任务总数
   - items: 任务数组，包含:
     * id/task_name/project_id
     * case_ids: 关联的用例ID列表
     * executor_id: 执行者ID
     * status: 任务状态
     * total_count/success_count/fail_count
     * progress: 执行进度(0-100)
     * create_time/update_time
3. 仅返回指定项目的任务""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "测试任务",
            "title": "执行测试任务-自动化执行引擎",
            "precondition": f"""1. 已登录系统
2. 存在待执行的测试任务(status=0)
3. 任务关联了测试用例
4. 测试执行引擎V2可用(TestExecutionEngineV2)""",
            "steps_json": [
                {"step": 1, "action": "构造POST请求到 /api/v1/test_task/{task_id}/run", "expected_result": "请求URL正确"},
                {"step": 2, "action": "添加Authorization头", "expected_result": "认证通过"},
                {"step": 3, "action": "发送请求触发任务执行", "expected_result": "执行引擎启动"},
                {"step": 4, "action": "监控执行进度", "expected_result": "逐步执行每个用例"}
            ],
            "expected_result": """1. HTTP状态码200
2. TestExecutionEngineV2开始执行任务:
   - 遍历任务关联的所有测试用例
   - 对每个用例执行测试步骤
   - 记录实际结果和执行状态
   - 更新test_results表(exec_status: 0pending/1running/2passed/3failed/4skipped)
3. 返回执行摘要:
   - task: 更新后的任务对象
   - summary: {total/pass/fail/skip/count, duration, pass_rate}
4. 任务status更新为执行完成状态
5. 记录started_at和completed_at时间""",
            "priority": 1,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "测试任务",
            "title": "获取任务执行摘要-统计数据准确性",
            "precondition": f"1. 已登录系统\n2. 测试任务(ID=17)已执行完成\n3. 有执行结果数据",
            "steps_json": [
                {"step": 1, "action": "构造GET请求到 /api/v1/test_task/17/summary", "expected_result": "请求URL正确"},
                {"step": 2, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"}
            ],
            "expected_result": """1. HTTP状态码200
2. 返回执行摘要数据:
   - task_id: 17
   - total: 总用例数
   - passed: 通过数
   - failed: 失败数
   - skipped: 跳过数
   - pass_rate: 通过率(百分比)
   - duration: 执行耗时(秒)
   - start_time: 开始时间
   - end_time: 结束时间
3. 统计数据与test_results表一致
4. 支持前端图表展示""",
            "priority": 2,
            "case_type": "API",
            "test_category": "api_automation"
        },
        {
            "module": "测试任务",
            "title": "删除测试任务-清理历史数据",
            "precondition": f"1. 已登录系统\n2. 存在可删除的测试任务",
            "steps_json": [
                {"step": 1, "action": "构造DELETE请求到 /api/v1/test_task/{task_id}", "expected_result": "请求URL正确"},
                {"step": 2, "action": "添加Authorization头并发送请求", "expected_result": "认证通过"}
            ],
            "expected_result": """1. HTTP状态码200
2. 返回: "测试任务删除成功"
3. test_tasks表删除该任务记录
4. 关联的test_results记录同时删除(级联或应用层处理)
5. 测试用例本身不被删除(任务和用例独立)""",
            "priority": 3,
            "case_type": "API",
            "test_category": "api_automation"
        },

        # ==================== 8. 前端业务流程测试-链接管理模块 (4个用例) ====================
        {
            "module": "链接管理",
            "title": "新增链接时验证添加人字段自动填充",
            "precondition": f"""1. 已登录洪恩早教机管理系统({TEST_ENV_URL})
2. 当前用户已登录，用户名为: {TEST_ACCOUNT}
3. 进入链接管理模块页面""",
            "steps_json": [
                {"step": 1, "action": f"打开浏览器访问 {TEST_ENV_URL}", "expected_result": "页面加载成功，显示登录页或首页"},
                {"step": 2, "action": f"使用账号{TEST_ACCOUNT}登录系统", "expected_result": "登录成功，进入系统主页"},
                {"step": 3, "action": "导航至链接管理模块", "expected_result": "进入链接管理页面，显示链接列表"},
                {"step": 4, "action": "点击'新增链接'按钮", "expected_result": "弹出新增链接对话框或跳转新增页面"},
                {"step": 5, "action": "检查表单中是否包含'添加人'字段", "expected_result": "表单中存在'添加人'字段"},
                {"step": 6, "action": "验证'添加人'字段的值是否自动填充为当前登录用户", "expected_result": "添加人字段值为当前用户名，且字段为只读或自动填充状态"}
            ],
            "expected_result": """1. 新增链接表单正确展示'添加人'字段
2. '添加人'字段自动填充当前操作用户的用户名
3. 字段值准确反映实际操作者身份
4. 用户无法手动修改添加人字段(若设计为只读)
5. 保存链接记录时，添加人信息正确写入数据库""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "链接管理",
            "title": "验证添加人字段在不同用户登录时的值变化",
            "precondition": f"""1. 系统中存在至少两个用户账号
2. 用户A和用户B均可登录系统
3. 链接管理模块支持多用户操作""",
            "steps_json": [
                {"step": 1, "action": "使用用户A账号登录系统", "expected_result": "用户A登录成功"},
                {"step": 2, "action": "进入链接管理并打开新增表单", "expected_result": "表单显示，添加人字段值为用户A"},
                {"step": 3, "action": "退出登录(不保存表单)", "expected_result": "退出成功"},
                {"step": 4, "action": "使用用户B账号登录系统", "expected_result": "用户B登录成功"},
                {"step": 5, "action": "进入链接管理并打开新增表单", "expected_result": "表单显示，添加人字段值为用户B"},
                {"step": 6, "action": "对比两次添加人字段的值", "expected_result": "值不同，分别对应各自登录用户"}
            ],
            "expected_result": """1. 添加人字段动态跟随当前登录用户变化
2. 用户A登录时显示用户A的名字
3. 用户B登录时显示用户B的名字
4. 切换用户后，添加人字段实时更新
5. 不会出现用户混淆或缓存问题""",
            "priority": 2,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "链接管理",
            "title": "链接列表展示添加人列信息",
            "precondition": f"""1. 已登录系统
2. 链接管理模块中已存在多条链接记录(由不同用户创建)""",
            "steps_json": [
                {"step": 1, "action": "进入链接管理模块", "expected_result": "页面加载成功"},
                {"step": 2, "action": "查看链接列表的表头列定义", "expected_result": "表头包含'添加人'列"},
                {"step": 3, "action": "检查每行链接记录的添加人列数据", "expected_result": "每条记录都显示了添加人信息"},
                {"step": 4, "action": "验证添加人信息与创建时的操作用户一致", "expected_result": "数据准确无误"}
            ],
            "expected_result": """1. 链接列表表格包含'添加人'列
2. 每条链接记录正确显示其创建者的用户名
3. 添加人信息清晰可见，便于追溯操作来源
4. 支持按添加人筛选或排序(若有此功能)""",
            "priority": 2,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "链接管理",
            "title": "编辑已有链接时添加人字段保持不变",
            "precondition": f"""1. 已登录系统(用户A)
2. 存在由用户A创建的链接记录""",
            "steps_json": [
                {"step": 1, "action": "进入链接管理模块", "expected_result": "页面加载成功"},
                {"step": 2, "action": "找到用户A创建的链接记录并点击编辑", "expected_result": "打开编辑表单"},
                {"step": 3, "action": "检查添加人字段的值", "expected_result": "添加人字段显示原始创建者(用户A)"},
                {"step": 4, "action": "修改链接的其他字段(如名称、URL等)", "expected_result": "其他字段可正常编辑"},
                {"step": 5, "action": "保存修改", "expected_result": "保存成功"},
                {"step": 6, "action": "再次查看该链接记录", "expected_result": "添加人仍为用户A，其他字段已更新"}
            ],
            "expected_result": """1. 编辑链接时，添加人字段保持原始值(创建者)
2. 不会被当前编辑者覆盖
3. 正确记录了最初的创建者身份
4. 其他字段的修改正常保存
5. 添加人字段的不可编辑性得到保证""",
            "priority": 2,
            "case_type": "UI",
            "test_category": "ui_automation"
        },

        # ==================== 9. 前端业务流程测试-设备清单模块 (4个用例) ====================
        {
            "module": "设备清单",
            "title": "验证设备清单页面导出按钮存在且可点击",
            "precondition": f"""1. 已登录洪恩早教机管理系统({TEST_ENV_URL})
2. 账号: {TEST_ACCOUNT}
3. 进入设备清单模块页面
4. 设备清单中有设备数据(至少1条)""",
            "steps_json": [
                {"step": 1, "action": f"打开浏览器访问 {TEST_ENV_URL}", "expected_result": "页面加载成功"},
                {"step": 2, "action": f"使用账号{TEST_ACCOUNT}登录系统", "expected_result": "登录成功"},
                {"step": 3, "action": "导航至设备清单模块", "expected_result": "进入设备清单页面，显示设备列表"},
                {"step": 4, "action": "查找页面上的'导出'按钮", "expected_result": "找到导出按钮，按钮可见且未被置灰(disabled)"}
            ],
            "expected_result": """1. 设备清单页面顶部或操作区域存在'导出'按钮
2. 按钮样式正常，可见可交互
3. 按钮位置合理(通常在列表上方工具栏)
4. 按钮上有明确的图标或文字标识""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "设备清单",
            "title": "导出全部设备数据-验证Excel文件生成",
            "precondition": f"""1. 已登录系统
2. 设备清单页面有设备数据
3. 导出功能可用""",
            "steps_json": [
                {"step": 1, "action": "进入设备清单页面", "expected_result": "页面加载完成"},
                {"step": 2, "action": "确认无筛选条件(显示全部数据)", "expected_result": "列表显示所有设备记录"},
                {"step": 3, "action": "点击'导出'按钮", "expected_result": "触发导出操作"},
                {"step": 4, "action": "等待导出完成，检查是否下载文件", "expected_result": "浏览器下载Excel文件"},
                {"step": 5, "action": "打开下载的Excel文件", "expected_result": "文件可正常打开"},
                {"step": 6, "action": "验证Excel中的数据行数与页面显示的总数一致", "expected_result": "数据量一致"}
            ],
            "expected_result": """1. 点击导出按钮后，系统生成Excel文件
2. 文件自动下载到本地
3. Excel文件包含设备清单的全部字段(设备名称、型号、状态等)
4. 数据行数等于页面显示的设备总数
5. 导出的数据与页面显示的数据一致(无遗漏无重复)
6. 文件名包含时间戳或标识信息""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "设备清单",
            "title": "筛选后导出-仅导出符合条件的设备数据",
            "precondition": f"""1. 已登录系统
2. 设备清单有多条不同状态的设备数据
3. 页面支持按条件筛选(如按状态、类型等)""",
            "steps_json": [
                {"step": 1, "action": "进入设备清单页面", "expected_result": "页面加载完成"},
                {"step": 2, "action": "设置筛选条件(例如: 设备状态=在线)", "expected_result": "列表刷新，仅显示在线设备"},
                {"step": 3, "action": "记录筛选后的数据条数", "expected_result": "记录数量N"},
                {"step": 4, "action": "点击'导出'按钮", "expected_result": "触发导出"},
                {"step": 5, "action": "下载并打开Excel文件", "expected_result": "文件下载成功"},
                {"step": 6, "action": "验证Excel中的数据行数为N", "expected_result": "仅包含筛选后的数据"}
            ],
            "expected_result": """1. 导出的Excel仅包含筛选后的设备数据
2. 数据行数与筛选结果一致
3. 不包含被筛选排除的设备记录
4. 导出的每条数据都符合筛选条件
5. 筛选条件和导出功能联动正确""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "设备清单",
            "title": "选中部分行后导出-仅导出选中设备",
            "precondition": f"""1. 已登录系统
2. 设备清单有多条设备数据
3. 列表支持复选框多选功能""",
            "steps_json": [
                {"step": 1, "action": "进入设备清单页面", "expected_result": "页面加载完成"},
                {"step": 2, "action": "勾选前3条设备记录的复选框", "expected_result": "3条记录被选中，高亮显示"},
                {"step": 3, "action": "点击'导出'按钮(此时应为'导出选中'或类似文案)", "expected_result": "触发选中项导出"},
                {"step": 4, "action": "下载并打开Excel文件", "expected_result": "文件下载成功"},
                {"step": 5, "action": "验证Excel中恰好有3条数据", "expected_result": "数据量为3条"},
                {"step": 6, "action": "验证这3条数据就是之前选中的设备", "expected_result": "数据内容匹配"}
            ],
            "expected_result": """1. 选中行后，导出功能智能识别为'导出选中项'
2. 导出的Excel仅包含选中的设备记录
3. 数据量精确等于选中数量
4. 导出数据的顺序可能与选中顺序一致
5. 未选中的设备不在导出文件中""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },

        # ==================== 10. 前端业务流程测试-个人中心法律协议 (4个用例) ====================
        {
            "module": "个人中心",
            "title": "验证个人中心页面存在法律协议入口",
            "precondition": f"""1. 已登录洪恩早教机管理系统({TEST_ENV_URL})
2. 账号: {TEST_ACCOUNT}
3. 能访问个人中心页面(通常通过点击头像或用户名进入)""",
            "steps_json": [
                {"step": 1, "action": f"打开浏览器访问 {TEST_ENV_URL}", "expected_result": "页面加载成功"},
                {"step": 2, "action": f"使用账号{TEST_ACCOUNT}登录系统", "expected_result": "登录成功，进入系统主页"},
                {"step": 3, "action": "点击页面右上角的用户头像或用户名", "expected_result": "展开下拉菜单或跳转个人中心"},
                {"step": 4, "action": "进入个人中心页面", "expected_result": "显示个人信息、设置等选项"},
                {"step": 5, "action": "查找'法律协议'入口链接或按钮", "expected_result": "找到法律协议入口，可见可点击"}
            ],
            "expected_result": """1. 个人中心页面存在'法律协议'入口
2. 入口形式为链接、按钮或菜单项
3. 入口位置合理(如在设置区域或底部链接区)
4. 入口文字清晰(如'法律协议'、'用户协议'、'隐私政策'等)
5. 入口样式正常，无明显UI异常""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "个人中心",
            "title": "点击法律协议入口进入详情页",
            "precondition": f"""1. 已登录系统
2. 个人中心页面已打开
3. 法律协议入口可见""",
            "steps_json": [
                {"step": 1, "action": "在个人中心页面找到法律协议入口", "expected_result": "定位到入口元素"},
                {"step": 2, "action": "点击法律协议入口", "expected_result": "页面跳转或弹出新窗口/对话框"},
                {"step": 3, "action": "验证是否进入法律协议详情页", "expected_result": "页面标题或内容显示法律协议相关信息"}
            ],
            "expected_result": """1. 点击后成功导航至法律协议详情页
2. 详情页包含以下内容:
   - 协议标题(如《用户服务协议》、《隐私政策》等)
   - 协议正文内容(条款和说明)
   - 发布日期或生效日期
   - 可能的版本号
3. 页面布局整洁，文字可读
4. 支持滚动查看完整内容""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "个人中心",
            "title": "法律协议详情页内容完整性验证",
            "precondition": f"""1. 已进入法律协议详情页
2. 协议内容已加载完成""",
            "steps_json": [
                {"step": 1, "action": "查看协议详情页的标题区域", "expected_result": "标题显示正确的协议名称"},
                {"step": 2, "action": "滚动页面阅读协议正文", "expected_result": "正文内容完整显示"},
                {"step": 3, "action": "检查协议是否包含必要条款", "expected_result": "包含用户权利义务、隐私说明等关键内容"},
                {"step": 4, "action": "验证页面底部是否有返回按钮或导航", "expected_result": "可以返回上一页"}
            ],
            "expected_result": """1. 协议详情页内容完整:
   - 标题准确反映协议类型
   - 正文无截断、无乱码
   - 包含必要的法律条款
2. 页面交互正常:
   - 支持滚动浏览
   - 有返回或关闭功能
   - 无死链或无法操作的元素
3. 内容格式规范:
   - 段落层次清晰
   - 重点内容可能有加粗或高亮""",
            "priority": 2,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "个人中心",
            "title": "未登录状态下访问法律协议的权限控制",
            "precondition": f"1. 未登录系统(或已退出登录)\n2. 尝试直接访问法律协议详情页URL",
            "steps_json": [
                {"step": 1, "action": "确保当前处于未登录状态(清除cookie或退出)", "expected_result": "未登录状态确认"},
                {"step": 2, "action": "直接在浏览器地址栏输入法律协议详情页URL(若可知)", "expected_result": "尝试访问页面"},
                {"step": 3, "action": "观察系统响应", "expected_result": "系统进行权限校验"}
            ],
            "expected_result": """1. 若法律协议需要登录才能查看:
   - 重定向到登录页面
   - 或显示401/403错误
   - 或显示提示"请先登录"
2. 若法律协议无需登录即可查看(公开信息):
   - 正常显示协议内容
   - 但个人中心其他功能不可用
3. 权限控制逻辑合理，符合安全要求""",
            "priority": 2,
            "case_type": "UI",
            "test_category": "ui_automation"
        },

        # ==================== 11. 前端业务流程测试-预装应用卸载拦截 (4个用例) ====================
        {
            "module": "预装应用管理",
            "title": "点击卸载预装应用时弹出拦截确认框",
            "precondition": f"""1. 已登录洪恩早教机管理系统({TEST_ENV_URL})
2. 账号: {TEST_ACCOUNT}
3. 进入应用管理或预装应用模块
4. 存在标记为'预装'的应用程序""",
            "steps_json": [
                {"step": 1, "action": f"打开浏览器访问 {TEST_ENV_URL}", "expected_result": "页面加载成功"},
                {"step": 2, "action": f"使用账号{TEST_ACCOUNT}登录系统", "expected_result": "登录成功"},
                {"step": 3, "action": "导航至应用管理/预装应用模块", "expected_result": "进入应用列表页面"},
                {"step": 4, "action": "找到标记为'预装'的应用", "expected_result": "定位到预装应用(可能有特殊标识)"},
                {"step": 5, "action": "点击该应用的'卸载'按钮", "expected_result": "触发卸载拦截逻辑"}
            ],
            "expected_result": """1. 点击卸载按钮后，不会直接执行卸载操作
2. 弹出确认提示框(dialog/modal/alert)
3. 提示框内容包括:
   - 提示标题(如"确认卸载"、"温馨提示"等)
   - 提示文字(说明这是预装应用，卸载可能影响某些功能)
   - 确认按钮(如"确定卸载"、"仍然卸载")
   - 取消按钮(如"取消"、"再想想")
4. 提示框样式醒目，引起用户注意""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "预装应用管理",
            "title": "在拦截确认框中点击确认-继续执行卸载",
            "precondition": f"""1. 已点击预装应用的卸载按钮
2. 拦截确认框已弹出""",
            "steps_json": [
                {"step": 1, "action": "查看确认框的提示内容", "expected_result": "清楚了解卸载后果"},
                {"step": 2, "action": "点击确认框中的'确定/仍然卸载'按钮", "expected_result": "确认卸载操作"},
                {"step": 3, "action": "等待卸载操作执行", "expected_result": "系统处理后端卸载请求"},
                {"step": 4, "action": "检查应用状态变化", "expected_result": "应用状态变为已卸载或从列表移除"}
            ],
            "expected_result": """1. 点击确认后，确认框关闭
2. 系统继续执行卸载流程
3. 应用被成功卸载(状态变更或列表移除)
4. 可能显示"卸载成功"提示消息
5. 操作日志记录此次卸载行为(含用户确认信息)""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "预装应用管理",
            "title": "在拦截确认框中点击取消-中止卸载操作",
            "precondition": f"""1. 已点击预装应用的卸载按钮
2. 拦截确认框已弹出""",
            "steps_json": [
                {"step": 1, "action": "查看确认框的提示内容", "expected_result": "提示信息清晰"},
                {"step": 2, "action": "点击确认框中的'取消/再想想'按钮", "expected_result": "选择不卸载"},
                {"step": 3, "action": "确认框关闭", "expected_result": "对话框消失"},
                {"step": 4, "action": "检查应用状态", "expected_result": "应用保持原状，未被卸载"}
            ],
            "expected_result": """1. 点击取消后，确认框立即关闭
2. 卸载操作中止，不执行任何卸载动作
3. 应用保持安装状态，列表中原样显示
4. 不产生卸载相关的后端请求
5. 不显示卸载成功/失败的提示
6. 用户可以继续使用该应用或再次尝试卸载""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "预装应用管理",
            "title": "普通(非预装)应用卸载时不弹出拦截框",
            "precondition": f"""1. 已登录系统
2. 应用列表中同时存在预装应用和普通(用户自安装)应用""",
            "steps_json": [
                {"step": 1, "action": "进入应用管理模块", "expected_result": "显示应用列表"},
                {"step": 2, "action": "区分预装应用和普通应用(通过标识或列表)", "expected_result": "能识别两类应用"},
                {"step": 3, "action": "找到普通(非预装)应用的卸载按钮", "expected_result": "定位到目标应用"},
                {"step": 4, "action": "点击普通应用的卸载按钮", "expected_result": "触发卸载"},
                {"step": 5, "action": "观察是否弹出拦截确认框", "expected_result": "判断是否有拦截"}
            ],
            "expected_result": """1. 普通应用点击卸载后:
   - 可能直接卸载(无拦截)
   - 或仅弹出简单的确认框(不含特殊的预装应用提示)
2. 不会出现针对预装应用的特殊拦截文案
3. 卸载流程比预装应用简单
4. 区分预装和普通应用的拦截逻辑正确""",
            "priority": 2,
            "case_type": "UI",
            "test_category": "ui_automation"
        },

        # ==================== 12. 产品线管理模块-基于现有测试点 (6个用例) ====================
        {
            "module": "产品线管理",
            "title": "验证产品线清单页面顶部新增表单展示",
            "precondition": f"""1. 已登录洪恩早教机管理系统({TEST_ENV_URL})
2. 账号: {TEST_ACCOUNT}
3. 进入产品线管理/产品线清单页面""",
            "steps_json": [
                {"step": 1, "action": f"打开浏览器访问 {TEST_ENV_URL}", "expected_result": "页面加载成功"},
                {"step": 2, "action": f"使用账号{TEST_ACCOUNT}登录系统", "expected_result": "登录成功"},
                {"step": 3, "action": "导航至产品线管理模块", "expected_result": "进入产品线清单页面"},
                {"step": 4, "action": "检查页面顶部区域", "expected_result": "观察到新增表单区域"},
                {"step": 5, "action": "验证表单包含以下元素:", "expected_result": "所有元素均存在"},
                {"step": 6, "action": "  a) 名称输入框", "expected_result": "输入框可见可输入"},
                {"step": 7, "action": "  b) 描述输入框(文本域)", "expected_result": "文本域可见可输入"},
                {"step": 8, "action": "  c) 取消按钮", "expected_result": "按钮可见可点击"},
                {"step": 9, "action": "  d) 创建按钮", "expected_result": "按钮可见可点击"}
            ],
            "expected_result": """1. 产品线清单页面顶部显示新增表单
2. 表单布局合理，四个元素排列整齐
3. 名称输入框为单行文本输入
4. 描述输入框为多行文本域(textarea)
5. 取消按钮和创建按钮位于表单右侧或下方
6. 表单默认状态: 输入框为空，按钮可交互
7. 表单下方为产品线列表区域""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "产品线管理",
            "title": "产品线名称为空时点击创建-验证必填校验",
            "precondition": f"1. 已进入产品线清单页面\n2. 新增表单可见\n3. 名称输入框为空",
            "steps_json": [
                {"step": 1, "action": "确认名称输入框为空(未输入任何内容)", "expected_result": "输入框为空"},
                {"step": 2, "action": "可在描述框输入任意内容(或不输入)", "expected_result": "描述可有可无"},
                {"step": 3, "action": "点击'创建'按钮", "expected_result": "触发表单提交和校验"},
                {"step": 4, "action": "观察页面反馈", "expected_result": "显示错误提示"}
            ],
            "expected_result": """1. 不提交创建请求到后端(前端拦截)
2. 名称输入框显示错误状态(红色边框或背景)
3. 在名称输入框附近显示提示文字: "请输入产品线名称"
4. 提示方式可能为: tooltip/提示文字/气泡提示
5. 表单不会刷新或清空(保留已输入的描述内容)
6. 产品线列表不受影响(无刷新无新增)""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "产品线管理",
            "title": "创建重名产品线-验证后端错误提示",
            "precondition": f"""1. 已进入产品线清单页面
2. 已存在一个名为"测试产品线A"的产品线(假设)
3. 知道已存在的产品线名称""",
            "steps_json": [
                {"step": 1, "action": "在名称输入框输入已存在的产品线名称(如: '测试产品线A')", "expected_result": "名称输入成功"},
                {"step": 2, "action": "在描述输入框输入任意描述内容", "expected_result": "描述输入成功"},
                {"step": 3, "action": "点击'创建'按钮", "expected_result": "发送创建请求到后端"},
                {"step": 4, "action": "等待后端响应", "expected_result": "返回错误信息"}
            ],
            "expected_result": """1. 后端返回错误(如400或自定义错误码)
2. 前端准确展示后端返回的错误信息
3. 错误信息示例: "产品线名称已存在"
4. 错误提示位置明显(如表单上方或名称输入框旁)
5. 表单不清空，用户可修改名称后重新提交
6. 产品线列表不刷新(因为创建失败)
7. 创建按钮恢复正常状态(结束loading)""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "产品线管理",
            "title": "成功创建产品线-验证完整流程和数据刷新",
            "precondition": f"""1. 已进入产品线清单页面
2. 准备好新的产品线名称(确保不重名)
3. 准备好描述内容""",
            "steps_json": [
                {"step": 1, "action": "在名称输入框输入新的产品线名称(如: '自动化测试产品线_{时间戳}')", "expected_result": "名称输入成功"},
                {"step": 2, "action": "在描述输入框输入描述(不超过49字符)", "expected_result": "描述输入成功，字符计数器更新"},
                {"step": 3, "action": "点击'创建'按钮", "expected_result": "按钮进入loading状态(防重复提交)"},
                {"step": 4, "action": "等待创建请求完成", "expected_result": "后端处理创建逻辑"},
                {"step": 5, "action": "观察表单变化", "expected_result": "表单清空"},
                {"step": 6, "action": "观察产品线列表变化", "expected_result": "列表刷新，新产品线出现"}
            ],
            "expected_result": """1. 创建按钮点击后立即显示loading状态(禁用或旋转图标)
2. 创建成功后:
   - 名称输入框清空
   - 描述输入框清空
   - 字符计数器重置为0/49
   - 创建按钮恢复可点击状态
3. 产品线列表自动刷新:
   - 新产品线记录出现在列表中(通常是第一条或最后一条)
   - 显示正确的名称和描述
   - 创建时间准确
4. 可能显示"创建成功"提示消息(toast/alert)
5. 整个流程流畅，用户体验良好""",
            "priority": 1,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "产品线管理",
            "title": "点击取消按钮-验证表单清空且列表不受影响",
            "precondition": f"""1. 已进入产品线清单页面
2. 在表单中已输入一些内容(名称和描述)""",
            "steps_json": [
                {"step": 1, "action": "在名称输入框输入任意名称(如: '临时名称')", "expected_result": "名称输入成功"},
                {"step": 2, "action": "在描述输入框输入任意描述(如: '临时描述内容')", "expected_result": "描述输入成功"},
                {"step": 3, "action": "记录当前产品线列表的内容或总数", "expected_result": "记录基准数据"},
                {"step": 4, "action": "点击'取消'按钮", "expected_result": "触发取消操作"},
                {"step": 5, "action": "检查表单字段状态", "expected_result": "表单已清空"},
                {"step": 6, "action": "对比产品线列表与之前记录", "expected_result": "列表无变化"}
            ],
            "expected_result": """1. 点击取消后:
   - 名称输入框清空(值为空)
   - 描述输入框清空(值为空)
   - 字符计数器重置为0/49
2. 产品线列表:
   - 不刷新(无网络请求或刷新动画)
   - 数据内容与取消前完全一致
   - 总数不变，排序不变
3. 取消操作仅影响表单，不影响列表数据
4. 用户可重新开始输入新的产品线信息""",
            "priority": 2,
            "case_type": "UI",
            "test_category": "ui_automation"
        },
        {
            "module": "产品线管理",
            "title": "描述字段字符限制和计数器验证",
            "precondition": f"1. 已进入产品线清单页面\n2. 新增表单可见\n3. 描述输入框有字符计数器",
            "steps_json": [
                {"step": 1, "action": "点击描述输入框获取焦点", "expected_result": "输入框激活"},
                {"step": 2, "action": "输入1个字符，观察计数器", "expected_result": "计数器显示1/49"},
                {"step": 3, "action": "继续输入至10个字符", "expected_result": "计数器显示10/49"},
                {"step": 4, "action": "尝试输入第50个字符(超过限制)", "expected_result": "无法输入或自动截断"},
                {"step": 5, "action": "验证maxlength属性", "expected_result": "HTML属性maxlength=49"},
                {"step": 6, "action": "删除字符，观察计数器递减", "expected_result": "计数器实时更新"}
            ],
            "expected_result": """1. 描述输入框有maxlength=49属性(HTML层面限制)
2. 字符计数器格式: 已输入字符数/49 (如 0/49, 10/49, 49/49)
3. 计数器随输入实时更新，无延迟
4. 达到49字符后无法继续输入(浏览器原生限制)
5. 计数器位置通常在输入框右下角或右上方
6. 计数器颜色可能在接近上限时变化(如变红提醒)
7. 粘贴超长文本时自动截断至49字符""",
            "priority": 2,
            "case_type": "UI",
            "test_category": "ui_automation"
        }
    ]

    return test_cases_data


def save_test_cases_to_db(test_cases_data):
    """将测试用例保存到数据库"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        saved_count = 0
        errors = []

        for idx, case_data in enumerate(test_cases_data, 1):
            try:
                # 生成用例编号
                case_no = f"CASE{PROJECT_ID}-{datetime.now().strftime('%Y%m%d%H%M%S')}{idx:03d}"

                # 插入测试用例
                insert_sql = """
                    INSERT INTO test_cases (
                        case_no, project_id, module, title, precondition,
                        steps_json, expected_result, priority, case_type,
                        test_category, generate_status, review_status,
                        create_time, update_time
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        NOW(), NOW()
                    )
                """

                cursor.execute(insert_sql, (
                    case_no,
                    PROJECT_ID,
                    case_data['module'],
                    case_data['title'],
                    case_data['precondition'],
                    json.dumps(case_data['steps_json'], ensure_ascii=False),
                    case_data['expected_result'],
                    case_data['priority'],
                    case_data['case_type'],
                    case_data.get('test_category', 'manual'),
                    1,  # generate_status: 1=生成成功
                    'pending'  # review_status: pending
                ))

                case_id = cursor.lastrowid

                # 插入测试步骤
                for step in case_data['steps_json']:
                    step_sql = """
                        INSERT INTO test_steps (
                            test_case_id, step_number, action,
                            expected_result, create_time, update_time
                        ) VALUES (%s, %s, %s, %s, NOW(), NOW())
                    """
                    cursor.execute(step_sql, (
                        case_id,
                        step['step'],
                        step['action'],
                        step['expected_result']
                    ))

                saved_count += 1
                print(f"[OK] #{idx:02d} | ID:{case_id:>4} | {case_no} | [{case_data['module']}] {case_data['title']}")

            except Exception as e:
                errors.append({
                    'index': idx,
                    'title': case_data['title'],
                    'error': str(e)
                })
                print(f"[FAIL] #{idx:02d} | {case_data['title']}: {e}")

        conn.commit()

        print("\n" + "=" * 80)
        print(f"测试用例生成完成!")
        print(f"=" * 80)
        print(f"成功保存: {saved_count}/{len(test_cases_data)} 个测试用例")
        print(f"失败数量: {len(errors)} 个")

        if errors:
            print("\n失败详情:")
            for err in errors:
                print(f"  - #{err['index']:02d} {err['title']}: {err['error']}")

        return saved_count, errors

    finally:
        cursor.close()
        conn.close()


def main():
    """主函数"""
    print("=" * 80)
    print("洪恩早教机项目(ID=3) 完整测试用例生成")
    print("=" * 80)
    print(f"项目名称: {PROJECT_NAME}")
    print(f"项目ID: {PROJECT_ID}")
    print(f"测试环境: {TEST_ENV_URL}")
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 生成测试用例数据
    print("\n[1/3] 设计测试用例...")
    test_cases_data = generate_test_cases()
    print(f"共设计 {len(test_cases_data)} 个测试用例")

    # 保存到数据库
    print("\n[2/3] 保存测试用例到数据库...")
    saved_count, errors = save_test_cases_to_db(test_cases_data)

    # 统计信息
    print("\n[3/3] 生成统计报告...")

    # 查询最终数据
    conn = get_db_connection()
    cursor = conn.cursor()

    # 统计各模块用例数量
    cursor.execute("""
        SELECT module, COUNT(*) as cnt
        FROM test_cases
        WHERE project_id = %s
        GROUP BY module
        ORDER BY cnt DESC
    """, (PROJECT_ID,))

    print("\n各模块用例分布:")
    print("-" * 50)
    for row in cursor.fetchall():
        print(f"  {row['module']:20s} : {row['cnt']:3d} 个")

    # 统计用例类型
    cursor.execute("""
        SELECT case_type, COUNT(*) as cnt
        FROM test_cases
        WHERE project_id = %s
        GROUP BY case_type
    """, (PROJECT_ID,))

    print("\n用例类型分布:")
    print("-" * 50)
    for row in cursor.fetchall():
        print(f"  {row['case_type']:10s} : {row['cnt']:3d} 个")

    # 统计优先级
    cursor.execute("""
        SELECT
            SUM(CASE WHEN priority = 1 THEN 1 ELSE 0 END) as high,
            SUM(CASE WHEN priority = 2 THEN 1 ELSE 0 END) as medium,
            SUM(CASE WHEN priority = 3 THEN 1 ELSE 0 END) as low
        FROM test_cases
        WHERE project_id = %s
    """, (PROJECT_ID,))
    prio = cursor.fetchone()

    print("\n优先级分布:")
    print("-" * 50)
    high = prio['high'] or 0
    medium = prio['medium'] or 0
    low = prio['low'] or 0
    print(f"  高(1)   : {high:3d} 个")
    print(f"  中(2)   : {medium:3d} 个")
    print(f"  低(3)   : {low:3d} 个")

    # 总数
    cursor.execute("SELECT COUNT(*) as total FROM test_cases WHERE project_id = %s", (PROJECT_ID,))
    total = cursor.fetchone()['total']

    print("\n" + "=" * 80)
    print(f"项目'{PROJECT_NAME}'测试用例总计: {total} 个")
    print(f"(本次新增: {saved_count} 个)")
    print("=" * 80)

    cursor.close()
    conn.close()

    return saved_count, errors


if __name__ == "__main__":
    main()
