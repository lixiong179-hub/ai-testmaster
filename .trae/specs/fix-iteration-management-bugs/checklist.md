# Checklist

## 后端API修复验证

- [x] 文件列表接口 `/api/v1/file/list/{project_id}` 正确接收并使用 iteration_id 参数进行数据库查询
- [x] UI原型项目列表接口 `/api/v1/ui-prototype/project/list/{project_id}` 正确接收并使用 iteration_id 参数进行数据库查询
- [x] 文件上传接口正确保存 iteration_id 到 ProjectFile 记录
- [x] UI原型上传接口正确保存 iteration_id 到 UIPrototypeProject 记录
- [x] 删除迭代时级联删除所有关联资源（ProjectFile、UIPrototypeProject、UIScreen）和物理文件

## 前端分页与筛选修复验证

- [x] resource-manage.vue 使用后端真分页（请求携带 page、page_size、iteration_id）
- [x] 迭代筛选状态管理清晰（null=全部、0=未分类、正数=具体迭代ID）
- [x] 点击"全部"选项显示项目下所有资源（跨迭代）
- [x] 点击"未分类"选项仅显示 iteration_id 为空的资源
- [x] 点击具体迭代仅显示该迭代下的资源
- [x] 切换迭代时分页重置到第1页
- [x] 分页组件显示正确的 total 数量

## 上传流程验证

- [x] 上传弹窗中显示迭代选择器下拉框
- [x] 在具体迭代视图下上传，默认选中当前迭代且可修改
- [x] 在"全部"视图下上传，必须选择目标迭代或明确选择"未分类"
- [x] 在"未分类"视图下上传，默认不关联迭代
- [x] 单文件上传成功后 iteration_id 正确保存
- [x] 批量UI原型上传成功后 iteration_id 正确保存
- [x] 上传完成后资源列表自动刷新并显示在正确的迭代下

## 子页面适配验证

- [x] upload.vue 页面支持从URL参数接收 iteration_id
- [x] upload.vue 页面上传表单包含迭代选择器
- [x] ui-prototype.vue 页面正确展示所属迭代信息
- [x] 从 resource-manage.vue 跳转到子页面时携带完整参数（包括 iteration_id）

## 资源操作功能验证

- [x] AI分析跳转携带完整的 iteration_id 和其他必要参数
- [x] 编辑非UI原型资源时可修改其归属的迭代
- [x] 编辑UI原型资源时跳转到 ui-prototype.vue 并携带迭代信息
- [x] 删除操作有明确的确认提示和结果反馈
- [x] 删除后资源列表自动刷新

## 用户体验优化验证

- [x] 迭代卡片显示该迭代下的资源统计数量
- [x] 无迭代时显示友好的空状态提示
- [x] 所有操作有明确的成功/失败消息提示
- [x] 页面初始化时项目和迭代加载顺序正确，无报错
- [x] 页面布局美观，无样式错乱

## 兼容性与边界情况验证

- [x] 旧数据（无 iteration_id 的资源）在"未分类"下正常显示
- [x] 无迭代的旧项目仍可正常使用（显示所有资源在"全部"下）
- [x] 大量资源时分页功能正常
- [x] 快速连续切换迭代不会导致数据混乱或请求错误
- [x] 网络请求失败时有合理的错误处理和用户提示
