describe('AI TestMaster 全流程系统测试', () => {
  const timestamp = new Date().getTime()
  const project1Name = `测试项目1_${timestamp}`
  const project2Name = `测试项目2_${timestamp}`
  let authToken: string

  before(() => {
    // 通过API登录获取token
    cy.request({
      method: 'POST',
      url: 'http://localhost:8001/api/v1/auth/login',
      body: {
        username: 'admin',
        password: 'password123'
      }
    }).then((response) => {
      expect(response.status).to.eq(200)
      expect(response.body.code).to.eq(200)
      authToken = response.body.data.access_token
      cy.log('获取到认证token')
    })
  })

  describe('步骤1: 登录系统', () => {
    it('应该成功登录并跳转到首页', () => {
      cy.visit('/login')
      cy.wait(1000)

      // 点击账号登录tab
      cy.get('.el-tabs__item').contains('账号登录').click()
      cy.wait(500)

      // 输入账号密码
      cy.get('input[placeholder*="账号"]').first().type('admin')
      cy.get('input[placeholder*="密码"]').first().type('password123')

      // 获取验证码
      cy.window().then((win) => {
        const code = win.localStorage.getItem('captcha') || '1234'
        cy.get('input[placeholder*="验证码"]').first().type(code)
      })

      // 点击登录
      cy.get('button').contains('登录').click()

      // 等待跳转
      cy.wait(3000)

      // 验证登录成功
      cy.url().should('include', '/home')
    })
  })

  describe('步骤2: 创建项目1', () => {
    it('应该成功创建项目1', () => {
      // 先访问登录页设置token，然后再跳转到项目页
      cy.visit('/login')
      cy.window().then((win) => {
        win.localStorage.setItem('token', authToken)
      })
      cy.visit('/home/project')
      cy.wait(2000)

      // 验证页面加载成功
      cy.contains('项目列表').should('be.visible')

      // 点击创建项目按钮
      cy.get('button').contains('创建项目').click()
      cy.wait(500)

      // 填写项目信息
      cy.get('input[placeholder*="项目名称"]').type(project1Name)
      cy.get('textarea[placeholder*="项目描述"]').type('这是测试项目1的描述，用于全流程验证')

      // 提交创建
      cy.get('button').contains('确定').click()

      // 验证项目创建成功
      cy.wait(2000)
      cy.contains(project1Name).should('be.visible')
    })
  })

  describe('步骤3: 项目1 - 查看详情', () => {
    it('应该能够查看项目1详情', () => {
      // 先访问登录页设置token
      cy.visit('/login')
      cy.window().then((win) => {
        win.localStorage.setItem('token', authToken)
      })
      cy.visit('/home/project')
      cy.wait(2000)

      // 找到项目1并点击查看按钮
      cy.contains(project1Name).closest('tr').find('button').contains('查看').click()
      cy.wait(2000)

      // 验证项目详情页显示
      cy.contains('项目详情').should('be.visible')
      cy.contains(project1Name).should('be.visible')
    })
  })

  describe('步骤4: 创建项目2', () => {
    it('应该成功创建项目2', () => {
      // 先访问登录页设置token
      cy.visit('/login')
      cy.window().then((win) => {
        win.localStorage.setItem('token', authToken)
      })
      cy.visit('/home/project')
      cy.wait(2000)

      // 点击创建项目按钮
      cy.get('button').contains('创建项目').click()
      cy.wait(500)

      // 填写项目信息
      cy.get('input[placeholder*="项目名称"]').type(project2Name)
      cy.get('textarea[placeholder*="项目描述"]').type('这是测试项目2的描述，用于多项目隔离验证')

      // 提交创建
      cy.get('button').contains('确定').click()

      // 验证项目创建成功
      cy.wait(2000)
      cy.contains(project2Name).should('be.visible')
    })
  })

  describe('步骤5: 验证多项目隔离', () => {
    it('项目1和项目2应该独立存在', () => {
      // 先访问登录页设置token
      cy.visit('/login')
      cy.window().then((win) => {
        win.localStorage.setItem('token', authToken)
      })
      cy.visit('/home/project')
      cy.wait(2000)

      // 验证两个项目都显示在列表中
      cy.contains(project1Name).should('be.visible')
      cy.contains(project2Name).should('be.visible')
    })

    it('项目1详情应该显示正确的项目名称', () => {
      // 先访问登录页设置token
      cy.visit('/login')
      cy.window().then((win) => {
        win.localStorage.setItem('token', authToken)
      })
      cy.visit('/home/project')
      cy.wait(2000)

      // 进入项目1详情
      cy.contains(project1Name).closest('tr').find('button').contains('查看').click()
      cy.wait(2000)

      // 验证显示的是项目1的名称
      cy.contains(project1Name).should('be.visible')

      // 验证不显示项目2的名称
      cy.contains(project2Name).should('not.exist')
    })

    it('项目2详情应该显示正确的项目名称', () => {
      // 先访问登录页设置token
      cy.visit('/login')
      cy.window().then((win) => {
        win.localStorage.setItem('token', authToken)
      })
      cy.visit('/home/project')
      cy.wait(2000)

      // 进入项目2详情
      cy.contains(project2Name).closest('tr').find('button').contains('查看').click()
      cy.wait(2000)

      // 验证显示的是项目2的名称
      cy.contains(project2Name).should('be.visible')

      // 验证不显示项目1的名称
      cy.contains(project1Name).should('not.exist')
    })
  })

  describe('步骤6: 验证权限控制', () => {
    it('清除token后应该无法访问项目页面', () => {
      // 先访问登录页设置token
      cy.visit('/login')
      cy.window().then((win) => {
        win.localStorage.setItem('token', authToken)
      })
      cy.visit('/home/project')
      cy.wait(2000)

      // 验证可以访问项目页面
      cy.contains('项目列表').should('be.visible')

      // 清除token
      cy.window().then((win) => {
        win.localStorage.removeItem('token')
      })

      // 刷新页面
      cy.reload()
      cy.wait(2000)

      // 验证被重定向到登录页
      cy.url().should('include', '/login')
    })

    it('未登录时访问API应该返回401', () => {
      // 尝试访问API（使用错误的token）
      cy.request({
        method: 'GET',
        url: 'http://localhost:8001/api/v1/project/list',
        headers: {
          'Authorization': 'Bearer invalid_token'
        },
        failOnStatusCode: false
      }).then((response) => {
        // 验证返回401未授权或422验证错误
        expect(response.status).to.be.oneOf([401, 422])
      })
    })
  })

  describe('步骤7: 重新登录并清理', () => {
    it('应该能够重新登录', () => {
      cy.visit('/login')
      cy.wait(1000)

      // 点击账号登录tab
      cy.get('.el-tabs__item').contains('账号登录').click()
      cy.wait(500)

      cy.get('input[placeholder*="账号"]').first().type('admin')
      cy.get('input[placeholder*="密码"]').first().type('password123')
      cy.window().then((win) => {
        const code = win.localStorage.getItem('captcha') || '1234'
        cy.get('input[placeholder*="验证码"]').first().type(code)
      })
      cy.get('button').contains('登录').click()
      cy.wait(3000)

      // 验证登录成功
      cy.url().should('include', '/home')
    })

    it('应该能够删除测试项目', () => {
      // 重新获取token
      cy.request({
        method: 'POST',
        url: 'http://localhost:8001/api/v1/auth/login',
        body: {
          username: 'admin',
          password: 'password123'
        }
      }).then((response) => {
        authToken = response.body.data.access_token
      })

      // 先访问登录页设置token
      cy.visit('/login')
      cy.window().then((win) => {
        win.localStorage.setItem('token', authToken)
      })
      cy.visit('/home/project')
      cy.wait(2000)

      // 删除项目1
      cy.contains(project1Name).closest('tr').find('button').contains('删除').click()
      cy.wait(500)
      cy.get('.el-message-box').find('button').contains('确定').click()
      cy.wait(1000)

      // 删除项目2
      cy.contains(project2Name).closest('tr').find('button').contains('删除').click()
      cy.wait(500)
      cy.get('.el-message-box').find('button').contains('确定').click()
      cy.wait(1000)

      // 验证项目已删除
      cy.contains(project1Name).should('not.exist')
      cy.contains(project2Name).should('not.exist')
    })
  })
})
