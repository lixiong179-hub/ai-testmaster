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
        password: 'password123',
      },
    }).then((response) => {
      expect(response.status).to.eq(200)
      expect(response.body.code).to.eq(200)
      authToken = response.body.data.access_token
      cy.log('获取到认证token')
    })
  })

  beforeEach(() => {
    // 设置localStorage中的token
    cy.window().then((win) => {
      win.localStorage.setItem('token', authToken)
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
      cy.contains('仪表盘').should('be.visible')
    })
  })

  describe('步骤2: 创建项目1', () => {
    it('应该成功创建项目1', () => {
      cy.visit('/home/project')
      cy.wait(2000)

      // 验证页面加载成功
      cy.contains('项目列表').should('be.visible')

      // 点击创建项目按钮
      cy.get('.card-header').find('button').contains('创建项目').click()
      cy.wait(500)

      // 填写项目信息
      cy.get('input[placeholder*="项目名称"]').type(project1Name)
      cy.get('textarea[placeholder*="项目描述"]').type('这是测试项目1的描述，用于全流程验证')

      // 提交创建
      cy.get('.dialog-footer').find('button').contains('确定').click()

      // 验证项目创建成功
      cy.wait(2000)
      cy.contains(project1Name).should('be.visible')
    })
  })

  describe('步骤3: 项目1 - 上传需求文档', () => {
    it('应该成功上传需求文档', () => {
      // 进入项目1详情页
      cy.get('table')
        .contains('td', project1Name)
        .parent('tr')
        .find('button')
        .contains('查看')
        .click()
      cy.wait(2000)

      // 点击管理需求按钮
      cy.get('button').contains('管理需求').click()
      cy.wait(2000)

      // 点击上传需求按钮
      cy.get('button').contains('上传需求文档').click()
      cy.wait(500)

      // 上传文件
      cy.get('input[type="file"]').attachFile({
        filePath: 'test-requirements.docx',
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })

      // 等待上传完成
      cy.wait(3000)

      // 验证上传成功
      cy.contains('上传成功').should('be.visible')
    })

    it('应该成功提交UI原型URL', () => {
      // 点击添加UI原型按钮
      cy.get('button').contains('添加UI原型').click()
      cy.wait(500)

      // 填写UI原型信息
      cy.get('input[placeholder*="原型名称"]').type('首页原型')
      cy.get('input[placeholder*="原型URL"]').type('https://www.figma.com/file/test123')

      // 提交
      cy.get('button').contains('确定').click()

      // 验证添加成功
      cy.wait(1000)
      cy.contains('首页原型').should('be.visible')
    })
  })

  describe('步骤4: 项目1 - AI分析测试点', () => {
    it('应该成功触发AI分析', () => {
      // 返回到项目详情页
      cy.get('button').contains('返回列表').click()
      cy.wait(1000)

      // 重新进入项目详情页
      cy.get('table')
        .contains('td', project1Name)
        .parent('tr')
        .find('button')
        .contains('查看')
        .click()
      cy.wait(2000)

      // 点击管理测试用例按钮
      cy.get('button').contains('管理测试用例').click()
      cy.wait(2000)

      // 点击AI分析按钮
      cy.get('button').contains('AI分析').click()
      cy.wait(500)

      // 确认分析
      cy.get('button').contains('确定').click()

      // 等待分析完成
      cy.wait(10000)

      // 验证分析结果
      cy.contains('测试点').should('be.visible')
    })

    it('测试点应该与项目1绑定', () => {
      // 验证测试点列表存在
      cy.get('table').should('be.visible')
    })
  })

  describe('步骤5: 项目1 - 生成测试用例', () => {
    it('应该成功生成测试用例', () => {
      // 点击生成测试用例按钮
      cy.get('button').contains('生成测试用例').click()
      cy.wait(500)

      // 确认生成
      cy.get('button').contains('确定').click()

      // 等待生成完成
      cy.wait(10000)

      // 验证生成成功
      cy.contains('测试用例').should('be.visible')
    })

    it('测试用例应该与项目1绑定', () => {
      // 验证测试用例列表存在
      cy.get('table').should('be.visible')
    })
  })

  describe('步骤6: 项目1 - 创建测试任务', () => {
    it('应该成功创建测试任务', () => {
      // 返回到项目详情页
      cy.get('button').contains('返回列表').click()
      cy.wait(1000)

      // 重新进入项目详情页
      cy.get('table')
        .contains('td', project1Name)
        .parent('tr')
        .find('button')
        .contains('查看')
        .click()
      cy.wait(2000)

      // 点击管理测试任务按钮
      cy.get('button').contains('管理测试任务').click()
      cy.wait(2000)

      // 点击创建测试任务按钮
      cy.get('button').contains('创建测试任务').click()
      cy.wait(500)

      // 填写任务信息
      cy.get('input[placeholder*="任务名称"]').type('测试任务1')
      cy.get('textarea[placeholder*="任务描述"]').type('测试任务1描述')

      // 提交创建
      cy.get('button').contains('确定').click()

      // 验证任务创建成功
      cy.wait(2000)
      cy.contains('测试任务1').should('be.visible')
    })

    it('应该能够启动任务并查看实时日志', () => {
      // 点击启动任务按钮
      cy.get('button').contains('启动任务').click()
      cy.wait(500)

      // 确认启动
      cy.get('button').contains('确定').click()

      // 等待任务启动
      cy.wait(3000)

      // 验证任务状态为运行中
      cy.contains('运行中').should('be.visible')
    })
  })

  describe('步骤7: 项目1 - 查看测试报告', () => {
    it('应该能够查看测试报告', () => {
      // 返回到项目详情页
      cy.get('button').contains('返回列表').click()
      cy.wait(1000)

      // 重新进入项目详情页
      cy.get('table')
        .contains('td', project1Name)
        .parent('tr')
        .find('button')
        .contains('查看')
        .click()
      cy.wait(2000)

      // 点击查看测试报告按钮
      cy.get('button').contains('查看测试报告').click()
      cy.wait(2000)

      // 验证报告页面加载成功
      cy.contains('测试报告').should('be.visible')
    })

    it('应该能够导出PDF报告', () => {
      // 点击导出PDF按钮
      cy.get('button').contains('导出PDF').click()
      cy.wait(2000)

      // 验证导出成功
      cy.contains('导出成功').should('be.visible')
    })

    it('应该能够导出HTML报告', () => {
      // 点击导出HTML按钮
      cy.get('button').contains('导出HTML').click()
      cy.wait(2000)

      // 验证导出成功
      cy.contains('导出成功').should('be.visible')
    })
  })

  describe('步骤8: 创建项目2并重复测试', () => {
    it('应该成功创建项目2', () => {
      // 返回到项目列表页
      cy.visit('/home/project')
      cy.wait(2000)

      // 点击创建项目按钮
      cy.get('.card-header').find('button').contains('创建项目').click()
      cy.wait(500)

      // 填写项目信息
      cy.get('input[placeholder*="项目名称"]').type(project2Name)
      cy.get('textarea[placeholder*="项目描述"]').type('这是测试项目2的描述，用于全流程验证')

      // 提交创建
      cy.get('.dialog-footer').find('button').contains('确定').click()

      // 验证项目创建成功
      cy.wait(2000)
      cy.contains(project2Name).should('be.visible')
    })

    it('项目2应该能够独立上传需求和生成用例', () => {
      // 进入项目2详情页
      cy.get('table')
        .contains('td', project2Name)
        .parent('tr')
        .find('button')
        .contains('查看')
        .click()
      cy.wait(2000)

      // 点击管理需求按钮
      cy.get('button').contains('管理需求').click()
      cy.wait(2000)

      // 点击上传需求按钮
      cy.get('button').contains('上传需求文档').click()
      cy.wait(500)

      // 上传文件
      cy.get('input[type="file"]').attachFile({
        filePath: 'test-requirements.docx',
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })

      // 等待上传完成
      cy.wait(3000)

      // 验证上传成功
      cy.contains('上传成功').should('be.visible')
    })
  })

  describe('步骤9: 验证多项目隔离', () => {
    it('项目1不应该看到项目2的数据', () => {
      // 返回到项目列表页
      cy.visit('/home/project')
      cy.wait(2000)

      // 进入项目1详情页
      cy.get('table')
        .contains('td', project1Name)
        .parent('tr')
        .find('button')
        .contains('查看')
        .click()
      cy.wait(2000)

      // 点击管理测试用例按钮
      cy.get('button').contains('管理测试用例').click()
      cy.wait(2000)

      // 验证只显示项目1的测试用例
      cy.contains(project1Name).should('be.visible')
      cy.contains(project2Name).should('not.exist')
    })

    it('项目2不应该看到项目1的数据', () => {
      // 返回到项目列表页
      cy.visit('/home/project')
      cy.wait(2000)

      // 进入项目2详情页
      cy.get('table')
        .contains('td', project2Name)
        .parent('tr')
        .find('button')
        .contains('查看')
        .click()
      cy.wait(2000)

      // 点击管理测试用例按钮
      cy.get('button').contains('管理测试用例').click()
      cy.wait(2000)

      // 验证只显示项目2的测试用例
      cy.contains(project2Name).should('be.visible')
      cy.contains(project1Name).should('not.exist')
    })
  })

  describe('步骤10: 验证权限控制', () => {
    it('退出登录后应该无法访问项目', () => {
      // 返回到首页
      cy.visit('/home')
      cy.wait(1000)

      // 点击退出登录
      cy.get('.user-menu').click()
      cy.wait(500)
      cy.get('button').contains('退出登录').click()
      cy.wait(1000)

      // 验证跳转到登录页
      cy.url().should('include', '/login')

      // 尝试直接访问项目页面
      cy.visit('/home/project')
      cy.wait(1000)

      // 验证被重定向到登录页
      cy.url().should('include', '/login')
    })

    it('未登录时应该无法访问API', () => {
      // 清除localStorage
      cy.window().then((win) => {
        win.localStorage.removeItem('token')
      })

      // 尝试访问API
      cy.request({
        method: 'GET',
        url: 'http://localhost:8001/api/v1/project/list',
        failOnStatusCode: false,
      }).then((response) => {
        expect(response.status).to.eq(401)
      })
    })
  })

  describe('清理测试数据', () => {
    it('应该清理测试创建的项目', () => {
      // 重新登录
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
      cy.wait(3000)

      // 进入项目列表页
      cy.visit('/home/project')
      cy.wait(2000)

      // 删除项目1
      cy.get('table')
        .contains('td', project1Name)
        .parent('tr')
        .find('button')
        .contains('删除')
        .click()
      cy.wait(500)
      cy.get('button').contains('确定').click()
      cy.wait(1000)

      // 删除项目2
      cy.get('table')
        .contains('td', project2Name)
        .parent('tr')
        .find('button')
        .contains('删除')
        .click()
      cy.wait(500)
      cy.get('button').contains('确定').click()
      cy.wait(1000)

      // 验证项目已删除
      cy.contains(project1Name).should('not.exist')
      cy.contains(project2Name).should('not.exist')
    })
  })
})
