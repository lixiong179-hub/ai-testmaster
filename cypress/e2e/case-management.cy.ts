describe('测试用例管理功能测试', () => {
  beforeEach(() => {
    cy.loginByApi()
    cy.visit('/home/case')
  })

  it('查看用例列表', () => {
    cy.url().should('include', '/case')
    cy.contains('测试用例列表')
    cy.contains('请选择项目后查看用例列表').should('exist')
  })

  it('搜索用例', () => {
    cy.get('.hero-actions .el-select').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.get('input[placeholder*="用例"]').type('测试')
    cy.get('button').contains('查询').click()
    cy.wait(1000)
    cy.contains('测试用例列表')
  })

  it('筛选用例类型', () => {
    cy.get('.hero-actions .el-select').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.get('.filter-row .el-select').eq(1).click()
    cy.get('.el-select-dropdown__item').contains('UI自动化').click()
    cy.wait(1000)
    cy.contains('测试用例列表')
  })

  it('分页功能', () => {
    cy.get('.hero-actions .el-select').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.get('.el-pagination').should('exist')
  })

  it('导出按钮', () => {
    cy.get('.hero-actions .el-select').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.get('button').contains('导出').should('exist')
  })
})
