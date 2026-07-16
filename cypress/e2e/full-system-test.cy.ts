type ApiEnvelope<T> = {
  code?: number
  data?: T
  message?: string
  msg?: string
}

type ProjectListItem = {
  id?: number
  project_id?: number
  name: string
  description?: string
}

type ProjectCreateData = {
  project_id?: number
  id?: number
  name?: string
}

type TestCaseCreateData = {
  id: number
  project_id?: number
  title?: string
}

type TaskCreateData = {
  task_id: number
  project_id?: number
  task_name?: string
  total_count?: number
}

describe('AI TestMaster 全流程系统测试', () => {
  const API_URL = Cypress.env('apiUrl') || 'http://127.0.0.1:8000'
  const timestamp = Date.now()
  const project1Name = `系统测试项目1_${timestamp}`
  const project2Name = `系统测试项目2_${timestamp}`
  const caseTitle = `系统测试用例_${timestamp}`
  const taskName = `系统测试任务_${timestamp}`

  let authToken = ''
  let project1Id = 0
  let project2Id = 0
  let caseId = 0
  let taskId = 0

  const authHeaders = () => ({ Authorization: `Bearer ${authToken}` })

  const expectApiSuccess = <T>(response: Cypress.Response<ApiEnvelope<T>>) => {
    expect(response.status).to.be.within(200, 299)
    return response.body.data as T
  }

  const apiRequest = <T>(
    method: 'GET' | 'POST' | 'DELETE',
    path: string,
    options: Partial<Cypress.RequestOptions> = {}
  ) =>
    cy.request<ApiEnvelope<T>>({
      method,
      url: `${API_URL}${path}`,
      headers: authHeaders(),
      failOnStatusCode: false,
      ...options,
    })

  const findProjectIdByName = (name: string) =>
    apiRequest<{ items: ProjectListItem[] }>('GET', '/api/v1/project/list', {
      qs: { page: 1, page_size: 1000 },
    }).then((response) => {
      const data = expectApiSuccess<{ items: ProjectListItem[] }>(response)
      const project = data.items.find((item) => item.name === name)
      expect(project, `project ${name}`).to.exist
      return Number(project?.id || project?.project_id)
    })

  const createProject = (name: string, description: string) =>
    apiRequest<ProjectCreateData>('POST', '/api/v1/project/', {
      body: {
        name,
        description,
        project_type: 'web',
      },
    }).then((response) => {
      const data = expectApiSuccess<ProjectCreateData>(response)
      const responseId = Number(data.project_id || data.id || 0)
      if (responseId > 0) return cy.wrap(responseId)
      return findProjectIdByName(name)
    })

  const deleteProject = (projectId: number) => {
    if (!projectId || !authToken) return cy.wrap(null)
    return apiRequest<unknown>('DELETE', `/api/v1/project/${projectId}`)
  }

  before(() => {
    cy.loginByApi().then(() => {
      authToken = String(Cypress.env('authToken') || '')
      expect(authToken).to.have.length.greaterThan(10)
    })
  })

  after(() => {
    cy.then(() => deleteProject(project1Id))
    cy.then(() => deleteProject(project2Id))
  })

  describe('步骤1: 认证与首页访问', () => {
    it('应该成功登录并进入受保护页面', () => {
      cy.login()
      cy.url().should('include', '/home')
      cy.window().then((win) => {
        expect(win.localStorage.getItem('token')).to.be.a('string').and.not.be.empty
      })
    })
  })

  describe('步骤2: 创建项目1并校验详情', () => {
    it('应该成功创建项目1', () => {
      createProject(project1Name, '用于全流程系统测试的项目1').then((id) => {
        project1Id = Number(id)
        expect(project1Id).to.be.greaterThan(0)

        apiRequest<ProjectListItem>('GET', `/api/v1/project/${project1Id}`).then((response) => {
          const data = expectApiSuccess<ProjectListItem>(response)
          expect(data.name).to.eq(project1Name)
        })
      })
    })
  })

  describe('步骤3: 项目1资源与测试资产契约', () => {
    it('项目1应该能创建测试用例并按项目查询', () => {
      apiRequest<TestCaseCreateData>('POST', '/api/v1/test-case/', {
        body: {
          project_id: project1Id,
          module: '系统测试',
          title: caseTitle,
          precondition: '管理员已登录且项目存在',
          steps: [
            {
              step: 1,
              action: '打开项目中心',
              expected_result: '项目中心正常展示',
            },
          ],
          expected_result: '核心页面可访问',
          priority: 2,
          case_type: 'ui_automation',
          generate_status: 1,
          lifecycle_status: 'active',
          target_device: 'web',
        },
      }).then((response) => {
        const data = expectApiSuccess<TestCaseCreateData>(response)
        caseId = Number(data.id)
        expect(caseId).to.be.greaterThan(0)
      })

      apiRequest<{ items: TestCaseCreateData[] }>('GET', '/api/v1/test-case/', {
        qs: { project_id: project1Id, page: 1, page_size: 50 },
      }).then((response) => {
        const data = expectApiSuccess<{ items: TestCaseCreateData[] }>(response)
        expect(
          data.items.some((item) => item.id === caseId),
          'case belongs to project1'
        ).to.eq(true)
      })
    })

    it('项目1应该能创建测试任务并绑定用例', () => {
      apiRequest<TaskCreateData>('POST', '/api/v1/test-task/', {
        body: {
          project_id: project1Id,
          task_name: taskName,
          description: '系统测试创建的最小任务',
          case_ids: [caseId],
        },
      }).then((response) => {
        const data = expectApiSuccess<TaskCreateData>(response)
        taskId = Number(data.task_id)
        expect(taskId).to.be.greaterThan(0)
        expect(data.project_id).to.eq(project1Id)
        expect(data.total_count).to.eq(1)
      })

      cy.then(() =>
        apiRequest<{
          task: {
            id: number
            project_id: number
            task_name: string
            case_ids?: number[]
          }
          results: unknown[]
        }>('GET', `/api/v1/test-task/${taskId}`, {
          qs: { project_id: project1Id },
        })
      ).then((response) => {
        const data = response.body as {
          task: {
            id: number
            project_id: number
            task_name: string
            case_ids?: number[]
          }
          results: unknown[]
        }
        expect(response.status).to.eq(200)
        expect(data.task.id).to.eq(taskId)
        expect(data.task.project_id).to.eq(project1Id)
        expect(data.task.task_name).to.eq(taskName)
        expect(data.results).to.have.length(1)
      })
    })
  })

  describe('步骤4: 创建项目2并验证多项目隔离', () => {
    it('应该成功创建项目2', () => {
      createProject(project2Name, '用于全流程系统测试的项目2').then((id) => {
        project2Id = Number(id)
        expect(project2Id).to.be.greaterThan(0)
        expect(project2Id).to.not.eq(project1Id)
      })
    })

    it('项目列表应包含两个独立项目', () => {
      findProjectIdByName(project1Name).then((id) => {
        expect(id).to.eq(project1Id)
      })
      findProjectIdByName(project2Name).then((id) => {
        expect(id).to.eq(project2Id)
      })
    })

    it('项目2不应看到项目1的测试用例', () => {
      apiRequest<{ items: TestCaseCreateData[] }>('GET', '/api/v1/test-case/', {
        qs: { project_id: project2Id, page: 1, page_size: 50 },
      }).then((response) => {
        const data = expectApiSuccess<{ items: TestCaseCreateData[] }>(response)
        expect(
          data.items.some((item) => item.id === caseId),
          'case isolated from project2'
        ).to.eq(false)
      })
    })
  })

  describe('步骤5: 核心页面和权限控制', () => {
    beforeEach(() => {
      cy.loginByApi()
    })

    it('核心业务页面应该可访问', () => {
      const pages = [
        { path: '/home/project', title: '项目中心' },
        { path: '/home/requirement', title: '资源中心' },
        { path: '/home/case/test-point-management', title: '测试点管理' },
        { path: '/home/case', title: '测试用例列表' },
        { path: '/home/case/ai-generate', title: '新增用例生成' },
        { path: '/home/task', title: /执行中心|测试任务列表/ },
        { path: '/home/report', title: '报告中心' },
      ]

      pages.forEach((page) => {
        cy.visit(page.path)
        cy.location('pathname', { timeout: 15000 }).should('eq', page.path)
        cy.contains(page.title, { timeout: 15000 }).should('be.visible')
        cy.get('.main-content').should('not.contain', '404').and('not.contain', '空白页')
      })
    })

    it('无效 token 访问 API 应该被拒绝', () => {
      cy.request({
        method: 'GET',
        url: `${API_URL}/api/v1/project/list`,
        headers: { Authorization: 'Bearer invalid_token' },
        failOnStatusCode: false,
      })
        .its('status')
        .should('be.oneOf', [401, 422])
    })

    it('退出登录后应该无法访问项目页面', () => {
      cy.visit('/home/project')
      cy.window().then((win) => {
        win.localStorage.removeItem('token')
        win.localStorage.removeItem('userInfo')
      })
      cy.visit('/home/project')
      cy.url().should('include', '/login')
    })
  })

  describe('步骤6: 清理测试数据', () => {
    it('应该删除测试创建的项目', () => {
      deleteProject(project1Id).its('status').should('be.oneOf', [200, 404])
      project1Id = 0

      deleteProject(project2Id).its('status').should('be.oneOf', [200, 404])
      project2Id = 0
    })
  })
})
