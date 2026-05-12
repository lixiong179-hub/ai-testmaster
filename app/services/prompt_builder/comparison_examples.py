"""正反用例对比示例 - 共享模块。

提供:
    - get_comparison_examples: 返回7组正反用例对比示例文本，支持中英文
"""


_COMPARISON_EXAMPLES_ZH = """## 正反用例对比（学习优秀写法，避免差劲写法）

【对比1-主流程】
❌差劲：测试拍照提交作文功能 | 前置：账号已登录，APP运行正常 | 步骤：进入页面→拍摄裁剪→点击提交 | 预期：页面正常→拍照正常→提交成功显示结果
问题：描述笼统无校验目标；前置条件缺网络/权限；步骤口语化；预期模糊无判定标准
✅优秀：联网+已授权，验证拍照裁剪提交完整流程 | 前置：账号已登录、相机权限允许、设备网络正常 | 步骤：1.点击进入中文作文批改模块 2.点击拍照拍摄作文并完成裁剪确认 3.点击去批改按钮提交图片 | 预期：1.模块页面加载正常功能入口完整 2.相机正常唤起图片裁剪完成并本地保存 3.提交请求正常发起成功跳转展示批改报告
优点：描述清晰目标明确；前置条件完整可稳定复现；步骤原子化；步骤与预期一一对应

【对比2-边界值】
❌差劲：测试拍照数量限制 | 前置：账号已登录 | 步骤：打开拍照页面→连续拍摄多张照片 | 预期：拍照页面正常→达到上限后禁止继续拍照
问题：未明确页数上限无量化标准；步骤模糊无固定复现路径；预期缺弹窗文案等校验点
✅优秀：验证最多3页拍摄限制，超出上限校验拦截提示 | 前置：账号已登录、相机权限开启、规则限制最多3页 | 步骤：1.进入作文拍照拍摄页面 2.依次拍摄并保存3张作文图片 3.再次点击拍摄按钮尝试拍摄第4页 | 预期：1.相机预览界面正常展示无闪退黑屏 2.3张图片全部保存成功底部预览栏正常展示 3.弹出页数上限提示无法触发第四次拍摄
优点：精准覆盖边界值；操作步骤量化复现性强；预期含界面+数据+弹窗多重校验

【对比3-异常场景】
❌差劲：无相机权限测试拍照 | 前置：相机权限禁止 | 步骤：点击进入拍照功能 | 预期：无法打开相机弹出提示
问题：未区分临时/永久拒绝场景覆盖不足；预期过于简单未校验弹窗按钮跳转
✅优秀：相机权限永久拒绝，校验权限拦截与引导弹窗 | 前置：账号已登录、系统关闭APP相机权限 | 步骤：1.点击中文作文批改拍照入口 | 预期：1.无法唤起相机预览自动弹出权限引导弹窗 2.弹窗包含提示文案、取消、前往设置按钮功能可用
优点：精准锁定异常场景；全量校验弹窗文案+按钮+跳转逻辑；预期具体可落地

【对比4-网络异常】
❌差劲：断网提交作文测试 | 前置：已拍好作文图片 | 步骤：关闭手机网络→点击提交批改 | 预期：网络关闭成功→提交失败提示网络错误
问题：未明确断网时机复现性差；预期缺加载状态重试等交互校验；未校验APP容错防崩溃
✅优秀：图片准备完成后断网，校验提交时网络异常处理 | 前置：账号已登录、已完成作文拍照保存 | 步骤：1.手动关闭WiFi与移动数据断开网络 2.点击去批改发起提交请求 | 预期：1.设备识别为无网络状态 2.请求终止弹出网络异常提示页面无卡死无长期加载
优点：场景贴近真实使用；兼顾功能校验与容错性；步骤和预期严格绑定

【对比5-引导弹窗】
❌差劲：测试关闭首页引导弹窗 | 前置：首次进入作文页面 | 步骤：等待弹窗出现→点击关闭按钮 | 预期：弹窗正常弹出→弹窗关闭页面正常使用
问题：前置条件不严谨无缓存限制说明；未校验UI文案样式；预期宽泛判定标准不一致
✅优秀：首次进入模块，验证引导弹窗展示关闭交互 | 前置：首次进入该模块无弹窗关闭缓存记录 | 步骤：1.进入中文作文批改首页 2.查看页面弹窗内容 3.点击弹窗关闭按钮 | 预期：1.页面加载完成后自动弹出新手引导弹窗 2.弹窗文案图片展示完整样式符合设计 3.弹窗正常关闭首页所有功能按钮可正常点击操作
优点：前置条件严谨区分首次/非首次；覆盖UI+文案+交互+联动多维度；标准统一适合团队协作

【对比6-Web端列表页】
❌差劲：测试版本列表页面加载 | 前置：账号已登录系统 | 步骤：1.点击左侧测试页面版本菜单 | 预期：1.页面可以正常打开没有报错
问题：前置缺浏览器/网络约束无法稳定复现；步骤单一无元素检查动作；预期模糊笼统无具体校验点无法做自动化断言；覆盖极低UI错乱元素缺失无法发现
✅优秀：验证测试页面版本列表页访问、元素及基础渲染展示 | 前置：账号已登录、浏览器网络正常、系统功能访问权限正常无弹窗遮罩阻挡 | 步骤：1.点击左侧导航栏「测试页面版本」菜单入口 2.等待页面全部资源加载完成 3.检查页面按钮、表格表头、分页控件展示状态 | 预期：1.菜单点击响应正常跳转至版本列表页面 2.页面无白屏无接口报错无样式错乱 3.核心功能按钮、表格列表、分页组件正常渲染展示
优点：前置只约束环境与权限不依赖业务数据任意环境可独立执行；步骤原子化动作清晰便于自动化元素定位；操作与预期逐条对应校验点明确可断言

【对比7-Web端交互闭环】
❌差劲：测试新建版本按钮功能 | 前置：进入版本管理列表页面 | 步骤：1.点击页面右上角新建版本按钮 | 预期：1.弹出新增窗口功能正常使用
问题：前置含操作步骤而非环境状态自动化无法直接执行；操作流程不完整只点击不校验弹窗关闭按钮状态；预期口语化无明确判定标准不支持自动化落地
✅优秀：验证新建版本按钮点击、弹窗弹出与取消关闭交互 | 前置：账号已登录、浏览器网络正常、系统功能访问权限正常 | 步骤：1.点击左侧导航栏「测试页面版本」菜单进入版本列表页面 2.点击页面右上角「新建版本」功能按钮 3.观察新增弹窗整体布局表单及操作按钮展示 4.点击弹窗取消按钮关闭新增弹窗 | 预期：1.菜单点击响应正常跳转至版本列表页面 2.按钮点击无延迟无重复触发交互响应正常 3.新增弹窗正常居中弹出页面布局控件展示无误 4.取消按钮可正常关闭弹窗列表页面原有状态保持不变
优点：步骤包含完整导航路径用例可独立自动化执行；全程仅操作前端控件无数据依赖用例完全解耦；交互流程完整闭环覆盖导航弹窗关闭全链路"""

_COMPARISON_EXAMPLES_EN = """## Good vs Bad Test Case Examples (learn from best practices)

[Comparison 1 - Main Flow]
❌ BAD: Test photo-taking and essay submission | Precondition: Logged in, app working | Steps: Enter page -> Take photo and crop -> Click submit | Expected: Page normal -> Photo normal -> Submit success shows result
Issues: Vague description without verification targets; Missing network/permission preconditions; Colloquial steps; Fuzzy expected results without measurable criteria
✅ GOOD: Verify complete photo-crop-submit flow with network & permissions | Precondition: Logged in, camera permission granted, device network connected | Steps: 1. Click to enter essay grading module 2. Click to take photo, capture essay, and confirm crop 3. Click submit button to upload image | Expected: 1. Module page loads correctly, all function entries present 2. Camera launches normally, image cropped and saved locally 3. Submit request sent successfully, navigates to grading report
Strengths: Clear description with explicit goals; Complete preconditions for stable reproduction; Atomic steps; One-to-one step-expected mapping

[Comparison 2 - Boundary Value]
❌ BAD: Test photo count limit | Precondition: Logged in | Steps: Open camera page -> Take multiple photos continuously | Expected: Camera page normal -> Block further photos at limit
Issues: No explicit page limit, no quantifiable standard; Vague steps without fixed reproduction path; Missing popup text verification in expected results
✅ GOOD: Verify max 3-page photo limit, validate limit exceeded interception and prompt | Precondition: Logged in, camera permission on, rule limits max 3 pages | Steps: 1. Enter essay photo capture page 2. Sequentially take and save 3 essay images 3. Click capture button again to try 4th page | Expected: 1. Camera preview displays normally without crash or black screen 2. All 3 images saved, bottom preview bar displays correctly 3. Page limit toast appears, 4th capture is blocked
Strengths: Precise boundary value coverage; Quantifiable steps with high reproducibility; Multi-layer verification covering UI, data, and popups

[Comparison 3 - Exception Scenario]
❌ BAD: Test photo without camera permission | Precondition: Camera permission denied | Steps: Click to enter photo function | Expected: Cannot open camera, shows prompt
Issues: No distinction between temporary/permanent denial; Expected too simple, missing popup button and navigation checks
✅ GOOD: Camera permission permanently denied, verify permission block and guidance popup | Precondition: Logged in, system camera permission disabled for app | Steps: 1. Click essay grading photo entry | Expected: 1. Camera preview cannot launch, permission guidance popup appears automatically 2. Popup contains guidance text, Cancel button, and Go to Settings button, all functional
Strengths: Precisely targets exception scenario; Full validation of popup text + buttons + navigation logic; Concrete and actionable expected results

[Comparison 4 - Network Error]
❌ BAD: Test offline essay submission | Precondition: Essay photo already taken | Steps: Turn off phone network -> Click submit for grading | Expected: Network off -> Submit fails, shows network error
Issues: Timing of network disconnect unclear, poor reproducibility; Missing loading state and retry interaction checks; No app crash resilience validation
✅ GOOD: Disconnect after photo ready, verify network error handling on submit | Precondition: Logged in, essay photo captured and saved | Steps: 1. Manually turn off WiFi and mobile data 2. Click submit to initiate request | Expected: 1. Device recognized as offline 2. Request terminated, network error prompt shown, page not frozen or stuck loading
Strengths: Realistic usage scenario; Covers both functional validation and fault tolerance; Steps and expectations strictly paired

[Comparison 5 - Guide Popup]
❌ BAD: Test closing homepage guide popup | Precondition: First time entering essay page | Steps: Wait for popup -> Click close button | Expected: Popup appears normally -> Popup closes, page usable
Issues: Precondition not rigorous, no cache restriction explanation; No UI text/style verification; Broad expected with inconsistent criteria
✅ GOOD: First entry into module, verify guide popup display and close interaction | Precondition: First time entering module, no popup close cache record | Steps: 1. Enter essay grading homepage 2. Review popup content 3. Click popup close button | Expected: 1. New user guide popup appears after page loads 2. Popup text and images displayed completely, style matches design 3. Popup closes normally, all homepage function buttons are clickable
Strengths: Rigorous precondition distinguishing first vs repeat visits; Covers UI + content + interaction + linkage; Unified standards for team collaboration

[Comparison 6 - Web List Page]
❌ BAD: Test version list page loading | Precondition: Logged in | Steps: 1. Click left sidebar version menu | Expected: 1. Page opens without errors
Issues: Missing browser/network constraints for stable reproduction; Single step without element inspection; Vague expected without specific checkpoints, cannot automate assertions; Low coverage, UI errors and missing elements undetectable
✅ GOOD: Verify version list page access, all elements and basic rendering | Precondition: Logged in, browser network normal, system access permissions normal, no popup overlays | Steps: 1. Click left navigation 'Version' menu entry 2. Wait for all page resources to load 3. Check page buttons, table headers, pagination controls display status | Expected: 1. Menu click responds, navigates to version list page 2. No white screen, no API errors, no style issues 3. Core function buttons, table list, pagination components render correctly
Strengths: Preconditions only constrain environment and permissions, no business data dependency, executable in any environment; Atomic steps with clear actions for automation element targeting; Operations and expectations mapped one-to-one with assertable checkpoints

[Comparison 7 - Web Interaction Loop]
❌ BAD: Test new version button functionality | Precondition: On version management list page | Steps: 1. Click top-right new version button | Expected: 1. New window pops up, functions usable
Issues: Precondition contains operation steps instead of environment state, cannot be executed by automation directly; Incomplete flow only clicks without checking popup close and button state; Colloquial expected without measurable criteria, not automation-ready
✅ GOOD: Verify new version button click, popup display and cancel-close interaction | Precondition: Logged in, browser network normal, system access permissions normal | Steps: 1. Click left navigation 'Version' menu to enter list page 2. Click top-right 'New Version' button 3. Observe popup layout, form, and action buttons 4. Click popup Cancel button to close | Expected: 1. Menu click responds, navigates to version list page 2. Button click has no delay or duplicate triggers, interaction normal 3. New popup appears centered, layout and controls display correctly 4. Cancel button closes popup, list page state remains unchanged
Strengths: Steps include full navigation path, case can be executed independently by automation; Only operates frontend controls with no data dependency, fully decoupled; Complete interaction loop covering navigation, popup open, and close"""


def get_comparison_examples(lang: str = "zh") -> str:
    """返回正反用例对比示例的完整文本。

    Args:
        lang: 语言代码，"zh" 返回中文，"en" 返回英文，默认 "zh"

    Returns:
        包含7组对比示例的字符串，含标题和所有对比内容。
    """
    if lang == "en":
        return _COMPARISON_EXAMPLES_EN
    return _COMPARISON_EXAMPLES_ZH
