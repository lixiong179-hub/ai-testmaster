import type { RouteRecordRaw } from 'vue-router'

const dynamicRoutes: RouteRecordRaw[] = [
  {
    path: 'user',
    name: 'UserManagement',
    component: () => import('../views/system/user/index.vue'),
    meta: { title: '用户管理', permission: 'user:list' },
  },
  {
    path: 'role',
    name: 'RoleManagement',
    component: () => import('../views/system/role/index.vue'),
    meta: { title: '角色管理', permission: 'role:list' },
  },
  {
    path: 'profile',
    name: 'Profile',
    component: () => import('../views/profile/index.vue'),
    meta: { title: '个人中心' },
  },
  {
    // Task9: 测试能力已迁移至项目详情页「测试能力」Tab（按 project_id 配置），
    // 旧 URL 重定向到项目详情并携带 tab=test-capability，避免书签失效。
    // 项目 ID 由 detail 页 resolveInitialProjectId 从 URL/store 兜底解析。
    path: 'test-capability',
    name: 'TestCapability',
    redirect: '/home/project/detail?tab=test-capability',
    meta: { title: '测试能力', permission: 'system:manage' },
  },
  {
    path: 'audit-log',
    name: 'AuditLog',
    component: () => import('../views/system/audit-log/index.vue'),
    meta: { title: '审计日志', permission: 'system:manage' },
  },
  {
    // Task8: 质量规则已迁移至项目详情页「质量规则」Tab（按 project_id 配置），
    // 旧 URL 重定向到项目详情并携带 tab=quality-rule，避免书签失效。
    // 项目 ID 由 detail 页 resolveInitialProjectId 从 URL/store 兜底解析。
    path: 'quality-rule',
    name: 'QualityRule',
    redirect: '/home/project/detail?tab=quality-rule',
    meta: { title: '质量规则配置', permission: 'system:manage' },
  },
  {
    path: 'feature-flag',
    name: 'FeatureFlag',
    component: () => import('../views/system/feature-flag/index.vue'),
    meta: { title: 'FeatureFlag管理', permission: 'system:manage' },
  },
  {
    // R1-3：Agent 可观测性闭环入口 —— 会话列表 / 消息流 / 工具调用与成本。
    // 挂在 /home/system 下，沿用 system:manage 权限（与审计日志同级）。
    path: 'agent-monitor',
    name: 'AgentSessionMonitor',
    component: () => import('@/views/agent/AgentSessionMonitor.vue'),
    meta: { title: 'Agent会话监控', permission: 'system:manage' },
  },
  {
    path: 'prompt-template',
    name: 'PromptTemplate',
    component: () => import('../views/system/prompt-template/index.vue'),
    meta: { title: 'Prompt模板管理', permission: 'system:manage' },
  },
]

export const routes: RouteRecordRaw[] = [
  // 根路径智能重定向：已登录 → 项目中心；未登录 → 登录页
  // 避免已登录用户访问 / 时被多余跳到 /login 再回跳
  {
    path: '/',
    redirect: () => {
      const token = localStorage.getItem('token')
      // 已登录用户默认进入工作台首页（Task 15）
      return token ? '/home/workbench' : '/login'
    },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/login/index.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('../layouts/MainLayout.vue'),
    // Task 15: /home 默认重定向到工作台首页
    redirect: '/home/workbench',
    meta: { title: '首页', requireAuth: true },
    children: [
      {
        // 工作台首页：项目概览 + 待评审 + 最近任务 + AI 成本趋势
        path: 'workbench',
        name: 'Workbench',
        component: () => import('../views/workbench/Workbench.vue'),
        meta: { title: '工作台', requireAuth: true },
      },
      { path: 'dashboard', name: 'Dashboard', redirect: { name: 'Workbench' } },
      // 旧 URL 兼容：/home/analysis → 资源中心需求分析
      { path: 'analysis', redirect: { name: 'RequirementAnalysis' } },
      {
        path: 'pipeline-dashboard',
        name: 'PipelineDashboard',
        component: () => import('@/views/admin/PipelineDashboard.vue'),
        meta: { title: 'Pipeline仪表盘', requireAuth: true },
      },
      {
        path: 'ai-cost-dashboard',
        name: 'AICostDashboard',
        component: () => import('@/views/admin/AICostDashboard.vue'),
        meta: { title: 'AI成本仪表盘', requireAuth: true },
      },
      {
        path: 'ab-test-dashboard',
        name: 'AbTestDashboard',
        component: () => import('@/views/admin/AbTestDashboard.vue'),
        meta: { title: 'A/B实验看板', requireAuth: true },
      },
      {
        path: 'system',
        name: 'System',
        meta: { title: '系统管理', permission: 'system:manage' },
        children: dynamicRoutes,
      },
      {
        path: 'project',
        name: 'ProjectManagement',
        meta: { title: '项目中心' },
        children: [
          {
            path: '',
            name: 'ProjectList',
            component: () => import('../views/project/ProjectList.vue'),
            meta: { title: '项目中心' },
          },
          {
            path: 'detail',
            name: 'ProjectDetail',
            component: () => import('../views/project/detail.vue'),
            meta: { title: '项目详情' },
          },
        ],
      },
      {
        path: 'quick-test',
        name: 'QuickTest',
        component: () => import('@/views/quick-test/QuickTest.vue'),
        meta: { requireAuth: true, title: '快速测试' },
      },
      {
        path: 'requirement',
        name: 'RequirementManagement',
        meta: { title: '资源中心' },
        children: [
          {
            path: '',
            name: 'RequirementResource',
            component: () => import('../views/requirement/resource-manage.vue'),
            meta: { title: '资源中心' },
          },
          {
            path: 'upload',
            name: 'RequirementUpload',
            component: () => import('../views/requirement/upload.vue'),
            meta: { title: '上传资源' },
          },
          {
            // 需求分析：复用资源中心页面（AI 分析入口位于资源列表），后续可独立为分析视图
            path: 'analysis',
            name: 'RequirementAnalysis',
            component: () => import('../views/requirement/resource-manage.vue'),
            meta: { title: '需求分析' },
          },
          {
            path: 'ui-prototype',
            name: 'UIPrototypeManage',
            component: () => import('../views/requirement/ui-prototype.vue'),
            meta: { title: 'UI原型详情' },
            // UI原型详情页是上下文相关页面，需要 project_id 和 prototype_project_id 参数
            // 从菜单直接进入时无参数，重定向到资源中心并筛选UI原型类型，引导用户选择具体原型
            beforeEnter: (to) => {
              const projectId = to.query.project_id
              const prototypeProjectId = to.query.prototype_project_id
              if (!projectId || !prototypeProjectId) {
                return {
                  name: 'RequirementResource',
                  query: { resource_type: 'ui_mockup' },
                }
              }
            },
          },
        ],
      },
      {
        path: 'self-healing',
        name: 'SelfHealingManagement',
        meta: { title: '自愈管理' },
        children: [
          {
            path: 'audits',
            name: 'SelfHealingAudits',
            component: () => import('@/views/self-healing/AuditList.vue'),
            meta: { title: '自愈审计', requireAuth: true },
          },
        ],
      },
      {
        path: 'case',
        name: 'CaseManagement',
        meta: { title: '测试资产' },
        children: [
          {
            path: '',
            name: 'CaseList',
            component: () => import('../views/case/TestCaseList.vue'),
            meta: { title: '用例列表' },
          },
          {
            path: 'smart-generate',
            name: 'SmartGenerate',
            component: () => import('../views/case/smart-generate.vue'),
            meta: { title: '智能生成用例' },
          },
          {
            path: 'migration',
            name: 'CaseMigration',
            component: () => import('../views/case/CaseMigration.vue'),
            meta: { title: '用例迁移' },
          },
          {
            path: 'test-point-management',
            name: 'TestPointManagement',
            component: () => import('../views/case/test-point-management/index.vue'),
            meta: { title: '测试点管理' },
          },
          {
            path: 'test-point-extract',
            name: 'TestPointExtract',
            component: () => import('../views/case/test-point-extract.vue'),
            meta: { title: '测试点提取向导' },
          },
          {
            path: 'case-refresh',
            name: 'CaseRefresh',
            component: () => import('../views/case/CaseRefresh.vue'),
            meta: { title: '保鲜建议' },
          },
          {
            path: 'detail/:caseId',
            name: 'CaseDetail',
            component: () => import('../views/case/CaseDetail.vue'),
            meta: { title: '用例详情' },
          },
          {
            path: 'quality/:caseId',
            name: 'CaseQualityAnalysis',
            component: () => import('../views/case/CaseQualityAnalysis.vue'),
            meta: { title: '用例质量分析' },
            beforeEnter: (to) => {
              const caseId = to.params.caseId
              if (caseId === '0' || !caseId) {
                return { name: 'CaseList', query: { hint: '请先选择具体用例再进入质量分析' } }
              }
            },
          },
          {
            path: 'pipeline/:runId',
            redirect: (to) => ({
              name: 'IterationPipelineProgress',
              params: { runId: to.params.runId },
            }),
          },
          {
            path: 'iteration/regression-generate',
            redirect: { name: 'IterationRegressionGenerate' },
          },
        ],
      },
      {
        path: 'task',
        name: 'TaskManagement',
        meta: { title: '执行中心' },
        children: [
          {
            path: '',
            name: 'TaskOverview',
            component: () => import('../views/task/TaskList.vue'),
            meta: { title: '执行中心' },
          },
          {
            path: 'list/:projectId',
            name: 'TaskList',
            component: () => import('../views/task/TaskList.vue'),
            meta: { title: '任务列表' },
          },
          {
            path: 'create/:projectId',
            name: 'TaskCreate',
            component: () => import('../views/task/TaskCreate.vue'),
            meta: { title: '创建任务' },
          },
          {
            path: 'detail/:taskId',
            name: 'TaskDetail',
            component: () => import('../views/task/TaskDetail.vue'),
            meta: { title: '任务详情' },
          },
          {
            path: 'execution/:taskId',
            name: 'TestExecution',
            component: () => import('../views/execution/TestExecution.vue'),
            meta: { title: '测试执行' },
          },
        ],
      },
      {
        // 执行中心：报告中心、缺陷管理统一归口（任务列表沿用 /home/task 不迁移）
        path: 'execution',
        name: 'ExecutionCenter',
        meta: { title: '执行中心' },
        children: [
          {
            path: 'report',
            name: 'ExecutionReportList',
            component: () => import('../views/report/ReportList.vue'),
            meta: { title: '报告中心', requireAuth: true },
          },
          {
            path: 'report/detail',
            name: 'ExecutionReportDetail',
            component: () => import('../views/report/ReportDetail.vue'),
            meta: { title: '报告详情', requireAuth: true },
          },
          {
            path: 'bug',
            name: 'ExecutionBugList',
            component: () => import('../views/bug/BugList.vue'),
            meta: { title: '缺陷管理', requireAuth: true },
          },
        ],
      },
      // 旧 URL 兼容：/home/report → /home/execution/report
      {
        path: 'report',
        name: 'ReportManagement',
        redirect: { name: 'ExecutionReportList' },
        children: [
          { path: 'detail', redirect: { name: 'ExecutionReportDetail' } },
        ],
      },
      // 旧 URL 兼容：/home/bug → /home/execution/bug
      {
        path: 'bug',
        name: 'BugManagement',
        redirect: { name: 'ExecutionBugList' },
      },
      {
        path: 'iteration',
        name: 'IterationManagement',
        meta: { title: '迭代中心' },
        children: [
          {
            path: 'list',
            name: 'IterationList',
            component: () => import('../views/iteration/IterationList.vue'),
            meta: { title: '迭代管理' },
          },
          {
            path: 'pipeline/:runId',
            name: 'IterationPipelineProgress',
            component: () => import('../views/iteration/PipelineProgress.vue'),
            meta: { title: 'Pipeline进度' },
          },
          {
            path: 'regression-generate',
            name: 'IterationRegressionGenerate',
            component: () => import('../views/iteration/RegressionGenerate.vue'),
            meta: { title: '回归变更分析' },
          },
          {
            path: 'review/:reviewId',
            name: 'IterationReviewInbox',
            component: () => import('../views/iteration/ReviewInbox.vue'),
            meta: { title: '评审 Inbox' },
          },
        ],
      },
    ],
  },
  // 404 兜底：未匹配的路由统一导向 NotFound，避免白屏
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/error/NotFound.vue'),
    meta: { title: '页面不存在' },
  },
]
