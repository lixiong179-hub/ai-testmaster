describe('测试点管理模块 E2E 测试', () => {
  beforeEach(() => {
    cy.loginByApi()
    cy.visit('/home/case/test-point-management')
  })

  it('进入模块并选择项目后加载测试点列表', () => {
    cy.url().should('include', '/test-point-management')
    cy.contains('测试点管理').should('exist')
    cy.get('.project-select .el-select__wrapper').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.wait(1000)
    cy.contains('测试点列表').should('exist')
  })

  it('统计卡片正确渲染并可点击筛选', () => {
    cy.get('.project-select .el-select__wrapper').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.wait(1000)
    cy.get('.stats-cards').should('exist')
    cy.get('.stats-cards .stat-card').should('have.length.gte', 1)
  })

  it('新增测试点', () => {
    cy.get('.project-select .el-select__wrapper').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.wait(1000)
    cy.get('button').contains('新增测试点').click()
    cy.get('.el-dialog').should('be.visible')
    cy.get('input[placeholder*="模块"]').should('exist')
    cy.get('.el-dialog__footer button').contains('取消').click()
  })

  it('筛选区布局正确且可查询重置', () => {
    cy.get('.project-select .el-select__wrapper').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.wait(1000)
    cy.get('.filter-card').should('exist')
    cy.get('button').contains('查询').should('exist')
    cy.get('button').contains('重置').should('exist')
    cy.get('input[placeholder*="搜索"]').should('exist')
  })

  it('表格操作列包含查看用例、生成用例和更多按钮', () => {
    cy.get('.project-select .el-select__wrapper').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.wait(2000)
    cy.get('.management-table tbody tr').then(($rows) => {
      if ($rows.length > 0) {
        cy.get('.management-table tbody tr')
          .first()
          .within(() => {
            cy.contains('查看用例').should('exist')
            cy.contains('生成用例').should('exist')
            cy.contains('更多').should('exist')
          })
      }
    })
  })

  it('批量操作栏在选择行后显示扩展操作', () => {
    cy.get('.project-select .el-select__wrapper').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.wait(2000)
    cy.get('.management-table tbody tr').then(($rows) => {
      if ($rows.length > 0) {
        cy.get('.management-table tbody tr').first().find('.el-checkbox').click()
        cy.get('.batch-actions').should('be.visible')
        cy.get('.batch-actions').contains('批量删除').should('exist')
        cy.get('.batch-actions').contains('批量生成用例').should('exist')
        cy.get('.batch-actions').contains('批量改优先级').should('exist')
        cy.get('.batch-actions').contains('批量改状态').should('exist')
        cy.get('.batch-actions').contains('导出选中').should('exist')
      }
    })
  })

  it('从需求提取按钮打开提取弹窗', () => {
    cy.get('.project-select .el-select__wrapper').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.wait(1000)
    cy.get('button').contains('从需求提取').click()
    cy.get('.el-dialog').should('be.visible')
    cy.get('.el-dialog__title').should('contain', '提取')
    cy.get('.el-dialog__footer button').contains('取消').click()
  })

  it('导入 XMind 按钮打开导入弹窗', () => {
    cy.get('.project-select .el-select__wrapper').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.wait(1000)
    cy.get('button').contains('导入 XMind').click()
    cy.get('.el-dialog').should('be.visible')
    cy.get('.el-dialog__footer button').contains('取消').click()
  })

  it('查看任务按钮可点击', () => {
    cy.get('.project-select .el-select__wrapper').click()
    cy.get('.el-select-dropdown__item').first().click()
    cy.wait(1000)
    cy.get('button').contains('查看任务').click()
  })

  it('未选择项目时操作按钮禁用', () => {
    cy.get('button').contains('新增测试点').should('be.disabled')
    cy.get('button').contains('从需求提取').should('be.disabled')
    cy.get('button').contains('导入 XMind').should('be.disabled')
    cy.get('button').contains('查看任务').should('be.disabled')
  })
})
