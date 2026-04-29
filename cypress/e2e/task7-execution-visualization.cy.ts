/**
 * Task 7: 执行过程可视化与视频录制 - 真实前端传参测试
 *
 * 测试范围:
 * - 可见模式配置API
 * - 执行控制API (开始、暂停、恢复、停止)
 * - 执行状态查询API
 * - 执行日志API
 * - 视频相关API
 * - 回放控制API
 *
 * 注意: 使用真实前端页面传参，不使用Mock
 */

describe('Task 7: 执行过程可视化与视频录制 - 真实联调测试', () => {
  // 登录并导航到测试执行页面
  beforeEach(() => {
    // 访问登录页面
    cy.visit('/login')
    cy.wait(1000)

    // 切换到账号登录
    cy.get('.el-tabs__item').contains('账号登录').click()
    cy.wait(500)

    // 输入登录信息
    cy.get('input[placeholder*="账号"]').first().type('admin')
    cy.get('input[placeholder*="密码"]').first().type('password123')

    // 获取验证码并输入
    cy.get('input[placeholder*="验证码"]')
      .first()
      .then(() => {
        const code = localStorage.getItem('captcha') || '1234'
        cy.get('input[placeholder*="验证码"]').first().type(code)
      })

    // 点击登录
    cy.get('button').contains('登录').click()

    // 等待登录成功
    cy.url().should('include', '/home')
    cy.contains('仪表盘')

    // 导航到任务列表
    cy.get('.el-sub-menu').contains('测试任务管理').click()
    cy.wait(500)
    cy.get('.el-menu-item').contains('任务列表').click()
    cy.url().should('include', '/task')
    cy.wait(1000)
  })

  describe('可见模式配置API测试', () => {
    it('获取全局可见模式配置 - 验证传参与返回', () => {
      // 拦截API请求
      cy.intercept('GET', '/api/visibility/config?level=global').as('getGlobalConfig')

      // 点击进入第一个任务的执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 点击可见模式配置按钮
      cy.get('button').contains('可见模式配置').click()
      cy.wait(500)

      // 等待API请求完成
      cy.wait('@getGlobalConfig').then((interception) => {
        // 验证请求参数
        expect(interception.request.query).to.have.property('level', 'global')

        // 验证返回数据格式
        const response = interception.response?.body
        expect(response).to.have.property('code', 200)
        expect(response).to.have.property('data')
        expect(response.data).to.have.property('headless')
        expect(response.data).to.have.property('record_video')
        expect(response.data).to.have.property('video_resolution')
        expect(response.data).to.have.property('video_fps')
      })

      // 关闭对话框
      cy.get('.el-dialog__headerbtn').click()
    })

    it('更新任务级别可见模式配置 - 验证传参与返回', () => {
      // 拦截API请求
      cy.intercept('PUT', '/api/visibility/config').as('updateConfig')

      // 点击进入第一个任务的执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 点击可见模式配置按钮
      cy.get('button').contains('可见模式配置').click()
      cy.wait(500)

      // 修改配置
      cy.get('.el-switch').first().click() // 切换无头模式
      cy.get('.el-switch').eq(1).click() // 启用视频录制

      // 选择分辨率
      cy.get('.el-select').click()
      cy.get('.el-select-dropdown__item').contains('1920x1080').click()

      // 保存配置
      cy.get('button').contains('保存配置').click()

      // 等待API请求完成
      cy.wait('@updateConfig').then((interception) => {
        // 验证请求参数
        const requestBody = interception.request.body
        expect(requestBody).to.have.property('level')
        expect(requestBody).to.have.property('headless')
        expect(requestBody).to.have.property('record_video')
        expect(requestBody).to.have.property('video_resolution')
        expect(requestBody).to.have.property('video_fps')

        // 验证返回数据
        const response = interception.response?.body
        expect(response).to.have.property('code', 200)
        expect(response).to.have.property('message')
      })
    })
  })

  describe('执行控制API测试', () => {
    it('开始执行 - 验证传参与返回', () => {
      // 拦截API请求
      cy.intercept('POST', '/api/execution/*/start').as('startExecution')

      // 点击进入第一个任务的执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 点击开始执行按钮
      cy.get('button').contains('开始执行').click()

      // 等待API请求完成
      cy.wait('@startExecution').then((interception) => {
        // 验证请求参数
        const requestBody = interception.request.body
        expect(requestBody).to.have.property('headless')
        expect(requestBody).to.have.property('record_video')

        // 验证返回数据
        const response = interception.response?.body
        expect(response).to.have.property('code', 200)
        expect(response).to.have.property('message')
        expect(response).to.have.property('data')
        expect(response.data).to.have.property('status')
      })
    })

    it('暂停执行 - 验证传参与返回', () => {
      // 拦截API请求
      cy.intercept('POST', '/api/execution/*/pause').as('pauseExecution')

      // 点击进入执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 先开始执行
      cy.get('button').contains('开始执行').click()
      cy.wait(1000)

      // 点击暂停按钮
      cy.get('button').contains('暂停').click()

      // 等待API请求完成
      cy.wait('@pauseExecution').then((interception) => {
        // 验证返回数据
        const response = interception.response?.body
        expect(response).to.have.property('code', 200)
        expect(response).to.have.property('message')
        expect(response.data).to.have.property('status', 'paused')
      })
    })

    it('恢复执行 - 验证传参与返回', () => {
      // 拦截API请求
      cy.intercept('POST', '/api/execution/*/resume').as('resumeExecution')

      // 点击进入执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 先开始执行然后暂停
      cy.get('button').contains('开始执行').click()
      cy.wait(1000)
      cy.get('button').contains('暂停').click()
      cy.wait(1000)

      // 点击恢复按钮
      cy.get('button').contains('恢复').click()

      // 等待API请求完成
      cy.wait('@resumeExecution').then((interception) => {
        // 验证返回数据
        const response = interception.response?.body
        expect(response).to.have.property('code', 200)
        expect(response).to.have.property('message')
        expect(response.data).to.have.property('status', 'running')
      })
    })

    it('停止执行 - 验证传参与返回', () => {
      // 拦截API请求
      cy.intercept('POST', '/api/execution/*/stop').as('stopExecution')

      // 点击进入执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 先开始执行
      cy.get('button').contains('开始执行').click()
      cy.wait(1000)

      // 点击停止按钮
      cy.get('button').contains('停止').click()

      // 确认停止
      cy.get('.el-message-box__btns').find('button').contains('确定').click()

      // 等待API请求完成
      cy.wait('@stopExecution').then((interception) => {
        // 验证返回数据
        const response = interception.response?.body
        expect(response).to.have.property('code', 200)
        expect(response).to.have.property('message')
        expect(response.data).to.have.property('status', 'stopped')
      })
    })
  })

  describe('执行状态与日志API测试', () => {
    it('获取执行状态 - 验证返回数据格式', () => {
      // 拦截API请求
      cy.intercept('GET', '/api/execution/*/status').as('getStatus')

      // 点击进入执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 开始执行
      cy.get('button').contains('开始执行').click()

      // 等待状态API请求
      cy.wait('@getStatus').then((interception) => {
        // 验证返回数据格式
        const response = interception.response?.body
        expect(response).to.have.property('code', 200)
        expect(response).to.have.property('data')
        expect(response.data).to.have.property('task_id')
        expect(response.data).to.have.property('status')
        expect(response.data).to.have.property('current_step')
        expect(response.data).to.have.property('total_steps')
        expect(response.data).to.have.property('progress')
      })
    })

    it('获取执行日志 - 验证返回数据格式', () => {
      // 拦截API请求
      cy.intercept('GET', '/api/execution/*/logs*').as('getLogs')

      // 点击进入执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 开始执行
      cy.get('button').contains('开始执行').click()
      cy.wait(2000)

      // 等待日志API请求
      cy.wait('@getLogs').then((interception) => {
        // 验证请求参数
        expect(interception.request.query).to.have.property('limit')

        // 验证返回数据格式
        const response = interception.response?.body
        expect(response).to.have.property('code', 200)
        expect(response).to.have.property('data')
        expect(response.data).to.have.property('logs')
        expect(response.data.logs).to.be.an('array')

        // 验证日志条目格式
        if (response.data.logs.length > 0) {
          const log = response.data.logs[0]
          expect(log).to.have.property('timestamp')
          expect(log).to.have.property('level')
          expect(log).to.have.property('message')
        }
      })
    })
  })

  describe('视频与回放API测试', () => {
    it('获取视频信息 - 验证返回数据格式', () => {
      // 拦截API请求
      cy.intercept('GET', '/api/execution/*/case/*/video/info').as('getVideoInfo')

      // 点击进入执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 切换到视频标签
      cy.get('.el-tabs__item').contains('执行视频').click()
      cy.wait(1000)

      // 等待视频信息API请求
      cy.wait('@getVideoInfo').then((interception) => {
        // 验证返回数据格式
        const response = interception.response?.body
        // 可能有视频或没有视频
        expect(response).to.have.property('code')

        if (response.code === 200) {
          expect(response).to.have.property('data')
          expect(response.data).to.have.property('file_path')
          expect(response.data).to.have.property('file_size')
          expect(response.data).to.have.property('duration')
        }
      })
    })

    it('获取回放会话信息 - 验证返回数据格式', () => {
      // 拦截API请求
      cy.intercept('GET', '/api/execution/replay/*').as('getReplaySession')

      // 点击进入执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 开始执行
      cy.get('button').contains('开始执行').click()
      cy.wait(2000)

      // 切换到回放控制标签
      cy.get('.el-tabs__item').contains('回放控制').click()
      cy.wait(500)

      // 等待回放会话API请求
      cy.wait('@getReplaySession').then((interception) => {
        // 验证返回数据格式
        const response = interception.response?.body
        expect(response).to.have.property('code', 200)
        expect(response).to.have.property('data')
        expect(response.data).to.have.property('execution_id')
        expect(response.data).to.have.property('total_duration')
        expect(response.data).to.have.property('has_video')
        expect(response.data).to.have.property('screenshot_count')
        expect(response.data).to.have.property('event_count')
      })
    })

    it('开始回放 - 验证传参与返回', () => {
      // 拦截API请求
      cy.intercept('POST', '/api/execution/replay/*/start').as('startReplay')

      // 点击进入执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 开始执行并等待完成
      cy.get('button').contains('开始执行').click()
      cy.wait(3000)

      // 切换到回放控制标签
      cy.get('.el-tabs__item').contains('回放控制').click()
      cy.wait(500)

      // 点击开始回放
      cy.get('button').contains('开始回放').click()

      // 等待API请求完成
      cy.wait('@startReplay').then((interception) => {
        // 验证返回数据
        const response = interception.response?.body
        expect(response).to.have.property('code', 200)
        expect(response).to.have.property('message')
      })
    })
  })

  describe('WebSocket实时更新测试', () => {
    it('验证WebSocket连接建立', () => {
      // 点击进入执行页面
      cy.get('.el-table__row').first().find('button').contains('执行').click()
      cy.wait(1000)

      // 开始执行
      cy.get('button').contains('开始执行').click()

      // 验证页面显示执行状态（通过WebSocket更新）
      cy.get('.execution-progress').should('be.visible')
      cy.get('.progress-text').should('contain', '步骤')

      // 验证步骤列表更新
      cy.get('.steps-list').should('be.visible')
    })
  })
})
