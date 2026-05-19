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
      { path: 'pipeline-dashboard', name: 'PipelineDashboard', component: () => import('@/views/admin/PipelineDashboard.vue'), meta: { title: 'Pipeline仪表盘', requireAuth: true } },
      { path: 'system', name: 'System', meta: { title: '系统管理', permission: 'system:manage' }, children: dynamicRoutes },
      {
        path: 'project', name: 'ProjectManagement', meta: { title: '项目管理' },
        children: [
          { path: '', name: 'ProjectList', component: () => import('../views/project/ProjectList.vue'), meta: { title: '项目列表' } },
          { path: 'detail', name: 'ProjectDetail', component: () => import('../views/project/detail.vue'), meta: { title: '项目详情' } },
        ],
      },
      {
        path: 'requirement', name: 'RequirementManagement', meta: { title: '资源管理' },
        children: [
          { path: '', name: 'RequirementResource', component: () => import('../views/requirement/resource-manage.vue'), meta: { title: '资源列表' } },
          { path: 'upload', name: 'RequirementUpload', component: () => import('../views/requirement/upload.vue'), meta: { title: '上传需求' } },
          { path: 'ui-prototype', name: 'UIPrototypeManage', component: () => import('../views/requirement/ui-prototype.vue'), meta: { title: 'UI原型管理' } },
        ],
      },
      {
        path: 'analysis', name: 'AnalysisManagement', meta: { title: '需求分析' },
        children: [
          { path: '', name: 'AnalysisPage', component: () => import('../views/analysis/AnalysisPage.vue'), meta: { title: '需求分析' } },
        ],
      },
      {
        path: 'case', name: 'CaseManagement', meta: { title: '测试用例管理' },
        children: [
          { path: '', name: 'CaseList', component: () => import('../views/case/TestCaseList.vue'), meta: { title: '用例列表' } },
          { path: 'ai-generate', name: 'CaseAIGenerate', component: () => import('../views/case/ai-generate.vue'), meta: { title: 'AI生成用例' } },
          { path: 'test-point-management', name: 'TestPointManagement', component: () => import('../views/case/test-point-management/index.vue'), meta: { title: '测试点管理' } },
          { path: 'test-point-extract', name: 'TestPointExtract', component: () => import('../views/case/test-point-extract.vue'), meta: { title: '测试点提取向导' } },
          { path: 'detail/:caseId', name: 'CaseDetail', component: () => import('../views/case/CaseDetail.vue'), meta: { title: '用例详情' } },
          { path: 'quality/:caseId', name: 'CaseQualityAnalysis', component: () => import('../views/case/CaseQualityAnalysis.vue'), meta: { title: '用例质量分析' } },
          { path: 'pipeline/:runId', name: 'PipelineProgress', component: () => import('../views/iteration/PipelineProgress.vue'), meta: { title: 'Pipeline 进度' } },
          { path: 'iteration/:iterationId/review/:reviewId', name: 'ReviewInbox', component: () => import('../views/iteration/ReviewInbox.vue'), meta: { title: '评审 Inbox' } },
          { path: 'iteration/regression-generate', name: 'RegressionGenerate', component: () => import('../views/iteration/RegressionGenerate.vue'), meta: { title: '旧项目变更分析' } },
        ],
      },
      {
        path: 'task', name: 'TaskManagement', meta: { title: '测试任务管理' },
        children: [
          { path: '', name: 'TaskListDefault', redirect: { name: 'ProjectList' } },
          { path: 'list/:projectId', name: 'TaskList', component: () => import('../views/task/TaskList.vue'), meta: { title: '任务列表' } },
          { path: 'create/:projectId', name: 'TaskCreate', component: () => import('../views/task/TaskCreate.vue'), meta: { title: '创建任务' } },
          { path: 'detail/:taskId', name: 'TaskDetail', component: () => import('../views/task/TaskDetail.vue'), meta: { title: '任务详情' } },
          { path: 'execution/:taskId', name: 'TestExecution', component: () => import('../views/execution/TestExecution.vue'), meta: { title: '测试执行' } },
        ],
      },
      {
        path: 'report', name: 'ReportManagement', meta: { title: '测试报告管理' },
        children: [
          { path: '', name: 'ReportList', component: () => import('../views/report/ReportList.vue'), meta: { title: '报告列表' } },
          { path: 'detail', name: 'ReportDetail', component: () => import('../views/report/ReportDetail.vue'), meta: { title: '报告详情' } },
        ],
      },
    ],
  },
]
