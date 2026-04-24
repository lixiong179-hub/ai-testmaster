import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

// 动态路由配置
const dynamicRoutes: RouteRecordRaw[] = [
  {
    path: 'user',
    name: 'UserManagement',
    component: () => import('../views/system/user/index.vue'),
    meta: {
      title: '用户管理',
      permission: 'user:list',
    },
  },
  {
    path: 'role',
    name: 'RoleManagement',
    component: () => import('../views/system/role/index.vue'),
    meta: {
      title: '角色管理',
      permission: 'role:list',
    },
  },
  {
    path: 'profile',
    name: 'Profile',
    component: () => import('../views/profile/index.vue'),
    meta: {
      title: '个人中心',
    },
  },
]

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/login',
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/login/index.vue'),
    meta: {
      title: '登录',
    },
  },
  {
    path: '/test',
    name: 'Test',
    component: () => import('../views/test/index.vue'),
    meta: {
      title: '测试',
    },
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/home/project',
    meta: {
      title: '首页',
      requireAuth: true,
    },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        redirect: { name: 'ProjectList' },
      },
      // 系统管理菜单
      {
        path: 'system',
        name: 'System',
        meta: {
          title: '系统管理',
          permission: 'system:manage',
        },
        children: dynamicRoutes,
      },
      // 项目管理菜单
      {
        path: 'project',
        name: 'ProjectManagement',
        meta: {
          title: '项目管理',
        },
        children: [
          {
            path: '',
            name: 'ProjectList',
            component: () => import('../views/project/ProjectList.vue'),
            meta: {
              title: '项目列表',
            },
          },
          {
            path: 'detail',
            name: 'ProjectDetail',
            component: () => import('../views/project/detail.vue'),
            meta: {
              title: '项目详情',
            },
          },
        ],
      },
      // 资源管理菜单
      {
        path: 'requirement',
        name: 'RequirementManagement',
        meta: {
          title: '资源管理',
        },
        children: [
          {
            path: '',
            name: 'RequirementResource',
            component: () => import('../views/requirement/resource-manage.vue'),
            meta: {
              title: '资源列表',
            },
          },
          {
            path: 'upload',
            name: 'RequirementUpload',
            component: () => import('../views/requirement/upload.vue'),
            meta: {
              title: '上传需求',
            },
          },
          {
            path: 'ui-prototype',
            name: 'UIPrototypeManage',
            component: () => import('../views/requirement/ui-prototype.vue'),
            meta: {
              title: 'UI原型管理',
            },
          },
        ],
      },
      // 需求分析菜单
      {
        path: 'analysis',
        name: 'AnalysisManagement',
        meta: {
          title: '需求分析',
        },
        children: [
          {
            path: '',
            name: 'AnalysisPage',
            component: () => import('../views/analysis/AnalysisPage.vue'),
            meta: {
              title: '需求分析',
            },
          },
        ],
      },
      // 测试用例管理菜单
      {
        path: 'case',
        name: 'CaseManagement',
        meta: {
          title: '测试用例管理',
        },
        children: [
          {
            path: '',
            name: 'CaseList',
            component: () => import('../views/case/TestCaseList.vue'),
            meta: {
              title: '用例列表',
            },
          },
          {
            path: 'ai-generate',
            name: 'CaseAIGenerate',
            component: () => import('../views/case/ai-generate.vue'),
            meta: {
              title: 'AI生成用例',
            },
          },
          {
            path: 'test-point-extract',
            name: 'TestPointExtract',
            component: () => import('../views/case/test-point-extract.vue'),
            meta: {
              title: '测试点提取向导',
            },
          },
          {
            path: 'test-point-management',
            name: 'TestPointManagement',
            component: () => import('../views/case/test-point-management/index.vue'),
            meta: {
              title: '测试点管理',
            },
          },
          {
            path: 'detail/:caseId',
            name: 'CaseDetail',
            component: () => import('../views/case/CaseDetail.vue'),
            meta: {
              title: '用例详情',
            },
          },
          {
            path: 'quality/:caseId',
            name: 'CaseQualityAnalysis',
            component: () => import('../views/case/CaseQualityAnalysis.vue'),
            meta: {
              title: '用例质量分析',
            },
          },
        ],
      },
      // 测试任务管理菜单
      {
        path: 'task',
        name: 'TaskManagement',
        meta: {
          title: '测试任务管理',
        },
        children: [
          {
            path: '',
            name: 'TaskListDefault',
            redirect: { name: 'TaskList', params: { projectId: '1' } },
          },
          {
            path: 'list/:projectId',
            name: 'TaskList',
            component: () => import('../views/task/TaskList.vue'),
            meta: {
              title: '任务列表',
            },
          },
          {
            path: 'create/:projectId',
            name: 'TaskCreate',
            component: () => import('../views/task/TaskCreate.vue'),
            meta: {
              title: '创建任务',
            },
          },
          {
            path: 'detail/:taskId',
            name: 'TaskDetail',
            component: () => import('../views/task/TaskDetail.vue'),
            meta: {
              title: '任务详情',
            },
          },
          {
            path: 'execution/:taskId',
            name: 'TestExecution',
            component: () => import('../views/execution/TestExecution.vue'),
            meta: {
              title: '测试执行',
            },
          },
        ],
      },
      // 测试报告管理菜单
      {
        path: 'report',
        name: 'ReportManagement',
        meta: {
          title: '测试报告管理',
        },
        children: [
          {
            path: '',
            name: 'ReportList',
            component: () => import('../views/report/ReportList.vue'),
            meta: {
              title: '报告列表',
            },
          },
          {
            path: 'detail',
            name: 'ReportDetail',
            component: () => import('../views/report/ReportDetail.vue'),
            meta: {
              title: '报告详情',
            },
          },
        ],
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return true
    const payload = JSON.parse(atob(parts[1]))
    if (!payload.exp) return false
    return Date.now() >= payload.exp * 1000
  } catch {
    return true
  }
}

function getUserPermissions(): string[] {
  const userInfo = localStorage.getItem('userInfo')
  if (!userInfo) return []
  try {
    const parsed = JSON.parse(userInfo)
    return parsed.permissions || []
  } catch {
    return []
  }
}

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'AI TestMaster'} - AI自动化测试平台`

  if (to.meta.requireAuth) {
    const token = localStorage.getItem('token')
    if (!token || isTokenExpired(token)) {
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      next('/login')
      return
    }

    if (to.meta.permission) {
      const permissions = getUserPermissions()
      if (!permissions.includes(to.meta.permission as string)) {
        next('/home/project')
        return
      }
    }

    next()
  } else {
    next()
  }
})

export default router
