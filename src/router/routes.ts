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
    path: 'test-capability',
    name: 'TestCapability',
    component: () => import('../views/system/test-capability/index.vue'),
    meta: { title: '测试能力', permission: 'system:manage' },
  },
  {
    path: 'audit-log',
    name: 'AuditLog',
    component: () => import('../views/system/audit-log/index.vue'),
    meta: { title: '审计日志', permission: 'system:manage' },
  },
  {
    path: 'quality-rule',
    name: 'QualityRule',
    component: () => import('../views/system/quality-rule/index.vue'),
    meta: { title: '质量规则配置', permission: 'system:manage' },
  },
  {
    path: 'feature-flag',
    name: 'FeatureFlag',
    component: () => import('../views/system/feature-flag/index.vue'),
    meta: { title: 'FeatureFlag管理', permission: 'system:manage' },
  },
]

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/login' },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/login/index.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/test',
    name: 'Test',
    component: () => import('../views/test/index.vue'),
    meta: { title: '测试' },
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/home/project',
    meta: { title: '首页', requireAuth: true },
    children: [
      { path: 'dashboard', name: 'Dashboard', redirect: { name: 'ProjectList' } },
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
            path: 'ui-prototype',
            name: 'UIPrototypeManage',
            component: () => import('../views/requirement/ui-prototype.vue'),
            meta: { title: 'UI原型详情' },
          },
        ],
      },
      {
        path: 'analysis',
        name: 'AnalysisManagement',
        meta: { title: '需求分析' },
        children: [
          {
            path: '',
            name: 'AnalysisPage',
            component: () => import('../views/analysis/AnalysisPage.vue'),
            meta: { title: '需求分析' },
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
            path: 'ai-generate',
            name: 'CaseAIGenerate',
            component: () => import('../views/case/ai-generate.vue'),
            meta: { title: 'AI生成用例' },
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
        path: 'report',
        name: 'ReportManagement',
        meta: { title: '报告中心' },
        children: [
          {
            path: '',
            name: 'ReportList',
            component: () => import('../views/report/ReportList.vue'),
            meta: { title: '报告中心' },
          },
          {
            path: 'detail',
            name: 'ReportDetail',
            component: () => import('../views/report/ReportDetail.vue'),
            meta: { title: '报告详情' },
          },
        ],
      },
      {
        path: 'iteration',
        name: 'IterationManagement',
        meta: { title: '迭代中心' },
        children: [
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
        ],
      },
    ],
  },
]
