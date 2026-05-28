describe('Task 7: 执行过程可视化与视频录制 - 前端传参测试', () => {
  const taskId = 70001

  const visitExecutionPage = (status = 'pending') => {
    cy.loginByApi()
    cy.intercept('GET', `**/api/v1/test_task/${taskId}*`, {
      statusCode: 200,
      body: {
        code: 200,
        message: 'ok',
        data: {
          status,
          current_step: status === 'running' ? 1 : 0,
          total_steps: 1,
          task: {
            id: taskId,
            task_name: '执行可视化测试任务',
            project_id: 1,
            status: status === 'running' ? 1 : status === 'completed' ? 2 : 0,
            total_count: 1,
            success_count: status === 'completed' ? 1 : 0,
            fail_count: 0,
            progress: status === 'completed' ? 100 : status === 'running' ? 50 : 0,
          },
        },
      },
    }).as('taskDetail')
    cy.intercept('GET', '**/api/v1/project/*', {
      statusCode: 200,
      body: {
        code: 200,
        data: {
          id: 1,
          name: '执行可视化项目',
          web_env_configs: { test: { url: 'http://127.0.0.1:3000/login' } },
        },
      },
    })
    cy.intercept('GET', '**/api/v1/test_task/*/summary*', {
      statusCode: 200,
      body: {
        code: 200,
        data: {
          logs: [{ timestamp: new Date().toISOString(), level: 'info', message: '执行日志' }],
        },
      },
    }).as('getSummary')
    cy.visit(`/home/task/execution/${taskId}?project_id=1`)
    cy.wait('@taskDetail')
  }

  describe('可见模式配置API测试', () => {
    it('获取并打开可见模式配置', () => {
      visitExecutionPage()
      cy.contains('button', '可见模式配置').click()
      cy.contains('.el-dialog__title', '可见模式配置').should('be.visible')
      cy.get('.el-dialog').within(() => {
        cy.contains('无头模式').should('exist')
        cy.contains('视频录制').should('exist')
      })
    })

    it('更新任务级别可见模式配置 - 验证传参与返回', () => {
      visitExecutionPage()
      cy.intercept('PUT', '**/api/v1/visibility/config', {
        statusCode: 200,
        body: { code: 200, message: 'ok', data: {} },
      }).as('updateConfig')
      cy.contains('button', '可见模式配置').click()
      cy.contains('button', '保存配置').click()
      cy.wait('@updateConfig').its('request.body').should('include', { level: 'task' })
    })
  })

  describe('执行控制API测试', () => {
    it('开始执行 - 验证传参与返回', () => {
      visitExecutionPage('pending')
      cy.intercept('POST', `**/api/v1/execution/${taskId}/start`, {
        statusCode: 200,
        body: { code: 200, message: 'ok', data: { status: 'running' } },
      }).as('startExecution')
      cy.contains('button', '开始执行').click()
      cy.wait('@startExecution').its('request.body').should('have.property', 'headless')
    })

    it('暂停按钮在运行状态下可触发对应接口', () => {
      visitExecutionPage('running')
      cy.intercept('POST', `**/api/v1/execution/${taskId}/pause`, {
        statusCode: 200,
        body: { code: 200, message: 'ok', data: { status: 'paused' } },
      }).as('pauseExecution')
      cy.contains('button', '暂停').click()
      cy.wait('@pauseExecution')
    })

    it('停止按钮在运行状态下可触发对应接口', () => {
      visitExecutionPage('running')
      cy.intercept('POST', `**/api/v1/execution/${taskId}/stop`, {
        statusCode: 200,
        body: { code: 200, message: 'ok', data: { status: 'stopped' } },
      }).as('stopExecution')
      cy.contains('button', '停止').click()
      cy.contains('.el-message-box__btns button', '确定').click()
      cy.wait('@stopExecution')
    })
  })

  describe('执行状态与日志API测试', () => {
    it('获取执行状态和日志 - 验证返回数据格式', () => {
      visitExecutionPage('running')
      cy.get('.execution-progress').should('be.visible')
      cy.wait('@getSummary')
      cy.contains('.log-message', '执行日志').should('exist')
    })
  })

  describe('视频与回放API测试', () => {
    it('执行视频页签和完成态回放控制可见', () => {
      visitExecutionPage('completed')
      cy.contains('.el-tabs__item', '执行视频').click()
      cy.contains('视频录制未启用或执行未完成').should('exist')
      cy.contains('.el-tabs__item', '回放控制').should('exist')
    })
  })
})
