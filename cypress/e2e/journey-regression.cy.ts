import { createPinia, setActivePinia } from 'pinia'
import { useTaskStore } from '../../src/store/task'
import request from '../../src/utils/request'

describe('业务链路回归：项目 -> 创建任务 -> 执行启动 -> 测试点管理', () => {
  const API_URL = 'http://127.0.0.1:8000'
  const timestamp = Date.now()
  const projectName = `链路回归项目_${timestamp}`
  const totalCaseCount = 105
  const caseTitle = `链路回归用例_${timestamp}_001`
  const overflowCaseTitle = `链路回归用例_${timestamp}_105`
  const taskName = `链路回归任务_${timestamp}`

  let authToken = ''
  const adminPassword = 'admin123'
  let projectId = 0
  let taskId = 0

  function buildCaseTitle(index: number) {
    return `链路回归用例_${timestamp}_${String(index).padStart(3, '0')}`
  }

  function authHeaders() {
    return {
      Authorization: `Bearer ${authToken}`,
    }
  }

  before(() => {
    cy.request({
      method: 'POST',
      url: `${API_URL}/api/v1/auth/login`,
      body: {
        username: 'admin',
        password: adminPassword,
      },
    })
      .then((loginResponse) => {
        expect(loginResponse.status).to.eq(200)
        authToken = loginResponse.body.data.access_token

        return cy.request({
          method: 'POST',
          url: `${API_URL}/api/v1/project`,
          headers: authHeaders(),
          body: {
            name: projectName,
            description: '用于项目 -> 任务 -> 执行 -> 测试点管理的真实链路回归',
            project_type: 'web',
            web_env_configs: {
              test: {
                url: 'http://127.0.0.1:3000/login',
                username: 'admin',
                password: adminPassword,
              },
            },
          },
        })
      })
      .then((projectResponse) => {
        expect(projectResponse.status).to.eq(200)
        projectId = projectResponse.body.data.project_id
      })
      .then(() => {
        const caseIndexes = Array.from({ length: totalCaseCount }, (_, index) => index + 1)

        return cy.wrap(caseIndexes).each((caseIndex) => {
          return cy
            .request({
              method: 'POST',
              url: `${API_URL}/api/v1/testCase`,
              headers: {
                ...authHeaders(),
                'Content-Type': 'application/json',
              },
              body: {
                project_id: projectId,
                module: caseIndex > 100 ? '超限模块' : '登录模块',
                title: buildCaseTitle(caseIndex),
                precondition: '管理员账号可用',
                steps: [
                  {
                    step: 1,
                    action: `打开页面并执行回归步骤 ${caseIndex}`,
                    param: '',
                    expected_result: '页面打开成功',
                  },
                ],
                expected_result: '可以进入登录流程',
                priority: 2,
                case_type: 'ui_automation',
                generate_status: 1,
              },
            })
            .then((caseResponse) => {
              expect(caseResponse.status).to.eq(200)
            })
        })
      })
  })

  after(() => {
    if (!projectId || !authToken) {
      return
    }

    cy.request({
      method: 'DELETE',
      url: `${API_URL}/api/v1/project/${projectId}`,
      headers: authHeaders(),
      failOnStatusCode: false,
    })
  })

  it('应串通入口、空状态、执行启动、返回路径与主按钮层级', () => {
    cy.login('admin', adminPassword)
    cy.visit('/home/project')

    cy.contains('.card-title', '项目列表').should('be.visible')

    cy.get('body').then(($body) => {
      if ($body.text().includes(projectName)) {
        cy.contains('tr', projectName).within(() => {
          cy.contains('button', '任务').should('be.visible')
          cy.contains('button', '测试点').should('be.visible')
          cy.contains('button', '任务').click()
        })
        return
      }

      cy.log('[WARN] 新建项目未出现在项目列表当前页，按项目ID继续后续链路')
      cy.visit(`/home/task/list/${projectId}`)
    })

    cy.url().should('include', `/home/task/list/${projectId}`)
    cy.contains('.card-title', '测试任务列表').should('be.visible')
    cy.contains('.task-empty-title', '当前项目还没有测试任务').should('be.visible')
    cy.contains('.task-empty-actions button', '先去测试点管理').should('be.visible')
    cy.contains('.task-empty-actions button', '创建首个任务')
      .should('be.visible')
      .and('have.class', 'el-button--primary')

    cy.contains('.task-empty-actions button', '先去测试点管理').click()

    cy.url().should('include', '/home/case/test-point-management')
    cy.url().should('include', `projectId=${projectId}`)
    cy.contains('.page-title', '测试点管理').should('be.visible')
    cy.get('.project-select').should('exist')
    cy.contains('.table-empty-title', '当前筛选下暂无测试点').should('exist')
    cy.contains('.table-empty-actions button', '新增测试点')
      .should('exist')
      .and('have.class', 'el-button--primary')
    cy.contains('.hero-action-group button', '查看任务').should('be.visible').click()

    cy.url().should('include', `/home/task/list/${projectId}`)
    cy.contains('button', '创建任务').should('be.visible').and('have.class', 'el-button--primary')
    cy.contains('.task-empty-actions button', '创建首个任务').click()

    cy.url().should('include', `/home/task/create/${projectId}`)
    cy.contains('.title', '创建测试任务').should('be.visible')
    cy.contains(caseTitle).should('be.visible')
    cy.get('.el-table__body-wrapper').should('contain.text', overflowCaseTitle)

    cy.intercept('POST', '**/api/v1/test_task').as('createTask')

    cy.get('input[placeholder="请输入任务名称"]').type(taskName)
    cy.get('.el-table__body-wrapper tbody tr').first().find('.el-checkbox').click()
    cy.contains('button', '创建任务').click()

    cy.wait('@createTask').then((interception) => {
      expect(interception.response?.statusCode).to.eq(200)
      taskId = interception.response?.body?.data?.task_id || 0
      expect(taskId).to.be.greaterThan(0)
    })

    cy.url().should('include', `/home/task/list/${projectId}`)
    cy.contains('.el-table__body-wrapper tbody tr', taskName).should('be.visible')
    cy.contains('.task-empty-title', '当前项目还没有测试任务').should('not.exist')

    cy.then(() => {
      cy.intercept('GET', `**/api/v1/execution/${taskId}/status`, {
        statusCode: 404,
        body: {
          detail: '执行状态不存在',
        },
      }).as('executionStatus404')

      cy.visit(`/home/task/execution/${taskId}?project_id=${projectId}`)
      cy.wait('@executionStatus404')

      cy.contains('.page-title', '测试执行').should('be.visible')
      cy.get('.env-selector').should('be.visible')
      cy.contains('.journey-actions button', '任务列表').should('be.visible')
      cy.contains('.journey-actions button', '测试点管理').should('be.visible')
      cy.contains('button', '开始执行').should('be.visible').and('have.class', 'el-button--primary')

      cy.intercept('POST', `**/api/v1/execution/${taskId}/start`).as('startExecution')
      cy.contains('button', '开始执行').click()

      cy.wait('@startExecution', { timeout: 120000 }).then((interception) => {
        expect(interception.response?.statusCode).to.eq(200)
      })
      cy.wait('@executionStatus404')

      cy.get('.execution-progress').should('exist')
      cy.get('.progress-info .el-tag')
        .invoke('text')
        .then((text) => {
          expect(text).not.to.include('等待执行')
        })

      cy.request({
        method: 'GET',
        url: `${API_URL}/api/v1/test_task/${taskId}`,
        headers: authHeaders(),
      }).then((taskDetailResponse) => {
        expect(taskDetailResponse.status).to.eq(200)
        const detailData = taskDetailResponse.body?.data || {}
        const taskData = detailData.task || detailData
        expect(taskData.status).to.not.eq(0)
      })

      cy.contains('button', '返回').click()
      cy.url().should('include', `/home/task/list/${projectId}`)
      cy.contains('.el-table__body-wrapper tbody tr', taskName).within(() => {
        cy.contains(/执行中|执行完成|执行失败|已停止/).should('exist')
      })

      cy.visit(`/home/task/execution/${taskId}?project_id=${projectId}`)
      cy.contains('.journey-actions button', '测试点管理').click()
    })

    cy.url().should('include', '/home/case/test-point-management')
    cy.url().should('include', `projectId=${projectId}`)
    cy.contains('.page-title', '测试点管理').should('be.visible')
    cy.get('.project-select').should('exist')
    cy.contains('.hero-action-group button', '查看任务').should('be.visible')
    cy.contains('.table-empty-title', '当前筛选下暂无测试点').should('exist')
  })

  it('应返回已解包的 taskStore 执行控制结果', () => {
    const mockedTaskId = 99991
    const mockedTaskName = `mocked-task-${timestamp}`
    const mockedTaskDetail = {
      id: mockedTaskId,
      task_name: mockedTaskName,
      project_id: projectId,
      description: '',
      case_ids: [],
      executor_id: 1,
      status: 1,
      start_time: null,
      end_time: null,
      success_count: 0,
      fail_count: 0,
      total_count: 1,
      progress: 0,
      create_time: new Date().toISOString(),
      update_time: new Date().toISOString(),
    }

    request.defaults.baseURL = Cypress.config('baseUrl')
    localStorage.setItem('token', authToken)

    cy.intercept('POST', `**/api/v1/test_task/${mockedTaskId}/start*`, {
      statusCode: 200,
      body: {
        code: 200,
        message: 'ok',
        data: {
          task_id: mockedTaskId,
          status: 'running',
        },
      },
    }).as('storeStartTask')

    cy.intercept('POST', `**/api/v1/test_task/${mockedTaskId}/stop*`, {
      statusCode: 200,
      body: {
        code: 200,
        message: 'ok',
        data: {
          task_id: mockedTaskId,
          status: 'stopped',
        },
      },
    }).as('storeStopTask')

    cy.intercept('POST', `**/api/v1/test_task/${mockedTaskId}/run*`, {
      statusCode: 200,
      body: {
        task: {
          ...mockedTaskDetail,
          status: 2,
        },
        summary: {
          task_id: mockedTaskId,
          total_cases: 1,
          passed_cases: 1,
          failed_cases: 0,
          blocked_cases: 0,
          total_duration_ms: 120,
          pass_rate: 100,
        },
      },
    }).as('storeRunTask')

    cy.intercept('GET', `**/api/v1/test_task/${mockedTaskId}*`, {
      statusCode: 200,
      body: {
        code: 200,
        message: 'ok',
        data: {
          task: mockedTaskDetail,
        },
      },
    }).as('storeTaskDetail')

    cy.then(async () => {
      setActivePinia(createPinia())
      const taskStore = useTaskStore()

      const startResult = await taskStore.startTask(mockedTaskId, projectId)
      expect(startResult).to.deep.include({
        task_id: mockedTaskId,
        status: 'running',
      })

      const stopResult = await taskStore.stopTask(mockedTaskId, projectId)
      expect(stopResult).to.deep.include({
        task_id: mockedTaskId,
        status: 'stopped',
      })

      const runResult = await taskStore.runTask(mockedTaskId, projectId)
      expect(runResult.task.id).to.eq(mockedTaskId)
      expect(runResult.summary.total_cases).to.eq(1)
      expect(runResult.summary.pass_rate).to.eq(100)
    })
  })
})
