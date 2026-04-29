describe('测试用例管理功能测试', () => {
  beforeEach(() => {
    cy.login()
    cy.navigateToCaseManagement()
  })

  it('查看用例列表', () => {
    cy.url().should('include', '/case')
    cy.contains('测试用例管理')
    cy.get('.el-table').should('exist')
  })

  it('搜索用例', () => {
    cy.get('input[placeholder*="用例"]').type('测试')
    cy.get('button').contains('搜索').click()
    cy.wait(1000)
    cy.contains('测试用例管理')
  })

  it('筛选用例类型', () => {
    cy.get('.el-select').first().click()
    cy.get('.el-select-dropdown__item').contains('功能测试').click()
    cy.wait(1000)
    cy.contains('测试用例管理')
  })

  it('分页功能', () => {
    cy.get('.el-pagination').should('exist')
  })

  it('新建用例', () => {
    cy.get('button').contains('新建用例').click()
    cy.url().should('include', '/case/detail')
  })

  it('AI生成按钮', () => {
    cy.get('button').contains('AI生成').should('exist')
  })
})
