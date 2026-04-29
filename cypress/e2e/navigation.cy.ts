describe('导航与跳转回归', () => {
  beforeEach(() => {
    // 避免后端未启动导致页面报错：按接口预期形状进行拦截
    cy.intercept('GET', '/api/api/v1/user*', {
      statusCode: 200,
      headers: { 'x-total-count': '0' },
      body: { data: [] },
    })
    cy.intercept('GET', '/api/api/v1/user/role*', { statusCode: 200, body: { data: [] } })

    const ok = { code: 200, msg: 'success', data: {} }
    cy.intercept('POST', '/api/**', ok)
    cy.intercept('PUT', '/api/**', ok)
    cy.intercept('DELETE', '/api/**', ok)

    // 绕过路由守卫
    cy.visit('/login', {
      onBeforeLoad(win) {
        win.localStorage.setItem('token', 'e2e-token')
      },
    })
    cy.visit('/home/dashboard')
    cy.url().should('include', '/home/dashboard')
  })

  it('侧边栏菜单可点击且路由正确', () => {
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-menu-item', '仪表盘').click()
    })
    cy.url().should('include', '/home/dashboard')

    // 项目管理
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-sub-menu__title', '项目管理').click()
      cy.contains('.el-menu-item', '项目列表').click()
    })
    cy.url().should('include', '/home/project')

    // 需求管理
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-sub-menu__title', '需求管理').click()
      cy.contains('.el-menu-item', '需求列表').click()
    })
    cy.url().should('include', '/home/requirement')
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-menu-item', '上传需求').click()
    })
    cy.url().should('include', '/home/requirement/upload')

    // 用例管理
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-sub-menu__title', '测试用例管理').click()
      cy.contains('.el-menu-item', '用例列表').click()
    })
    cy.url().should('include', '/home/case')
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-menu-item', 'AI生成用例').click()
    })
    cy.url().should('include', '/home/case/ai-generate')

    // 任务管理（默认重定向到 list/1）
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-sub-menu__title', '测试任务管理').click()
      cy.contains('li.el-menu-item', '任务列表').click({ force: true })
    })
    cy.url().should('include', '/home/task')

    // 报告
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-menu-item', '测试报告').click()
    })
    cy.url().should('include', '/home/report')

    // 系统管理
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-sub-menu__title', '系统管理').click()
      cy.contains('.el-menu-item', '用户管理').click()
    })
    cy.url().should('include', '/home/system/user')
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-menu-item', '角色管理').click()
    })
    cy.url().should('include', '/home/system/role')
  })
})
