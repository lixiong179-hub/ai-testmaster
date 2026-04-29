describe('全流程操作验证测试', () => {
  beforeEach(() => {
    cy.visit('/')
    cy.wait(1000)
    cy.get('.el-tabs__item').contains('账号登录').click()
    cy.wait(500)
  })

  it('登录系统', () => {
    cy.get('input[placeholder*="账号"]').first().type('admin')
    cy.get('input[placeholder*="密码"]').first().type('password123')
    cy.get('input[placeholder*="验证码"]')
      .first()
      .then(() => {
        const code = localStorage.getItem('captcha') || '1234'
        cy.get('input[placeholder*="验证码"]').first().type(code)
      })
    cy.get('button').contains('登录').click()
    cy.url().should('include', '/home')
    cy.contains('仪表盘')
  })

  it('创建项目1', () => {
    cy.get('.el-menu-item').contains('项目管理').click()
    cy.url().should('include', '/project')
    cy.get('button').contains('新建项目').click()
    cy.get('input[placeholder*="项目名称"]').type('项目1')
    cy.get('textarea[placeholder*="项目描述"]').type('测试项目1')
    cy.get('button').contains('确定').click()
    cy.contains('项目1')
  })

  it('创建项目2', () => {
    cy.get('button').contains('新建项目').click()
    cy.get('input[placeholder*="项目名称"]').type('项目2')
    cy.get('textarea[placeholder*="项目描述"]').type('测试项目2')
    cy.get('button').contains('确定').click()
    cy.contains('项目2')
  })

  it('项目1：上传需求文档和提交UI原型URL', () => {
    cy.contains('项目1').click()
    cy.url().should('include', '/project/detail')
    cy.get('button').contains('上传需求文档').click()
    // 这里需要模拟文件上传
    cy.get('button').contains('提交UI原型URL').click()
    cy.get('input[placeholder*="UI原型URL"]').type('https://www.figma.com')
    cy.get('button').contains('确定').click()
  })

  it('项目1：触发AI分析', () => {
    cy.get('button').contains('AI分析').click()
    cy.wait(10000)
    cy.contains('分析完成')
  })

  it('项目1：生成测试用例', () => {
    cy.get('button').contains('生成测试用例').click()
    cy.wait(10000)
    cy.contains('生成完成')
  })

  it('项目1：创建测试任务', () => {
    cy.get('button').contains('创建测试任务').click()
    cy.get('input[placeholder*="任务名称"]').type('测试任务1')
    cy.get('button').contains('选择用例').click()
    cy.get('.el-checkbox__input').first().click()
    cy.get('button').contains('确定').click()
    cy.get('button').contains('开始执行').click()
    cy.wait(5000)
  })

  it('项目1：查看测试报告', () => {
    cy.get('button').contains('查看报告').click()
    cy.url().should('include', '/report')
    cy.get('button').contains('导出PDF').click()
    cy.get('button').contains('导出HTML').click()
  })

  it('验证项目隔离', () => {
    cy.get('.el-menu-item').contains('项目管理').click()
    cy.contains('项目2').click()
    cy.url().should('include', '/project/detail')
    // 验证项目2中看不到项目1的数据
    cy.contains('项目1').should('not.exist')
  })

  it('验证权限', () => {
    cy.get('.el-dropdown').click()
    cy.get('.el-dropdown-menu__item').contains('退出登录').click()
    cy.url().should('include', '/login')
    cy.visit('/home')
    cy.url().should('include', '/login')
  })
})
