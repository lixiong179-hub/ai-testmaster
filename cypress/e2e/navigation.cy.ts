describe('导航与跳转回归', () => {
  beforeEach(() => {
    cy.loginByApi()
    cy.visit('/home/project')
    cy.url().should('include', '/home/project')
  })

  it('侧边栏菜单可点击且路由正确', () => {
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-menu-item', '项目中心').click()
    })
    cy.url().should('include', '/home/project')

    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-menu-item', '资源中心').click()
    })
    cy.url().should('include', '/home/requirement')

    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-sub-menu__title', '测试资产').click()
      cy.contains('.el-menu-item', '用例列表').click()
    })
    cy.url().should('include', '/home/case')
    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-menu-item', 'AI生成用例').click()
    })
    cy.url().should('include', '/home/case/ai-generate')

    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-menu-item', '执行中心').click()
    })
    cy.url().should('include', '/home/task')

    cy.get('.sidebar-menu').within(() => {
      cy.contains('.el-menu-item', '报告中心').click()
    })
    cy.url().should('include', '/home/report')

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
