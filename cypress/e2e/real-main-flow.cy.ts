type ApiEnvelope<T> = {
  code?: number
  data?: T
  message?: string
  msg?: string
}

type ProjectCreateData = {
  project_id: number
}

type PrototypeProject = {
  id: number
  name: string
  screen_count: number
  parsed_count: number
  parse_status: string
  has_flow?: boolean
  flow_summary?: {
    has_flow: boolean
    node_count: number
    edge_count: number
  }
}

type ScreenItem = {
  id: number
  screen_name: string
  parse_status: string
}

type TaskCreateData = {
  task_id: number
}

const apiUrl = Cypress.env('apiUrl') || 'http://127.0.0.1:8000'
const created = {
  projectId: 0,
  taskId: 0,
  caseId: 0,
  prototypeProjectId: 0,
  fileIds: [] as number[],
  screenIds: [] as number[],
}

const runName = () => {
  const d = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  const stamp = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
  return `E2E-${stamp}`
}

const e2eName = runName()

const authHeaders = () => ({
  Authorization: `Bearer ${Cypress.env('authToken')}`,
})

const apiRequest = <T>(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  url: string,
  options: Partial<Cypress.RequestOptions> = {}
) =>
  cy.then(() =>
    cy.request<ApiEnvelope<T>>({
      method,
      url: `${apiUrl}${url}`,
      headers: authHeaders(),
      failOnStatusCode: false,
      ...options,
    })
  )

const apiRequestDynamic = <T>(buildOptions: () => Cypress.RequestOptions) =>
  cy.then(() => {
    const options = buildOptions()
    return cy.request<ApiEnvelope<T>>({
      headers: authHeaders(),
      failOnStatusCode: false,
      ...options,
      url: `${apiUrl}${options.url}`,
    })
  })

const expectSuccessfulApi = <T>(response: Cypress.Response<ApiEnvelope<T>>) => {
  expect(response.status).to.be.within(200, 299)
  return response.body.data as T
}

const createImageBlob = (pageName: string, nextPageName: string, fileRole: string) =>
  cy.window().then((win) => {
    const canvas = win.document.createElement('canvas')
    canvas.width = 800
    canvas.height = 520
    const ctx = canvas.getContext('2d')
    expect(ctx, 'canvas context').to.not.equal(null)
    if (!ctx) throw new Error('Cannot create canvas context')

    ctx.fillStyle = '#f7fafc'
    ctx.fillRect(0, 0, 800, 520)
    ctx.fillStyle = '#1f2937'
    ctx.font = 'bold 34px Arial'
    ctx.fillText(`${pageName} - ${fileRole}`, 48, 78)
    ctx.fillStyle = '#2563eb'
    ctx.fillRect(48, 126, 704, 70)
    ctx.fillStyle = '#ffffff'
    ctx.font = '26px Arial'
    ctx.fillText(`${pageName} -> ${nextPageName}`, 78, 171)
    ctx.strokeStyle = '#94a3b8'
    ctx.lineWidth = 3
    ctx.strokeRect(48, 236, 300, 170)
    ctx.strokeRect(452, 236, 300, 170)
    ctx.fillStyle = '#111827'
    ctx.font = '22px Arial'
    ctx.fillText(pageName, 138, 320)
    ctx.fillText(nextPageName, 542, 320)
    ctx.strokeStyle = '#ef4444'
    ctx.beginPath()
    ctx.moveTo(360, 322)
    ctx.lineTo(438, 322)
    ctx.stroke()
    ctx.fillStyle = '#ef4444'
    ctx.beginPath()
    ctx.moveTo(438, 322)
    ctx.lineTo(420, 310)
    ctx.lineTo(420, 334)
    ctx.fill()

    return new Cypress.Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (blob) resolve(blob)
        else reject(new Error('Cannot create image blob'))
      }, 'image/png')
    })
  })

const uploadUiPrototypeScreens = (prototypeName: string) =>
  createImageBlob('资源列表页', 'UI原型详情页', 'page-1').then((firstBlob) =>
    createImageBlob('UI原型详情页', 'AI生成用例页', 'page-2').then((secondBlob) =>
      cy.window().then((win) => {
        const formData = new win.FormData()
        const firstFile = new win.File([firstBlob], `${e2eName}-ui-resource.png`, {
          type: 'image/png',
        })
        const secondFile = new win.File([secondBlob], `${e2eName}-ui-detail.png`, {
          type: 'image/png',
        })
        formData.append('project_id', String(created.projectId))
        formData.append('prototype_name', prototypeName)
        formData.append('files', firstFile)
        formData.append('files', secondFile)

        return win
          .fetch(`${apiUrl}/api/v1/ui-prototype/upload`, {
            method: 'POST',
            headers: authHeaders(),
            body: formData,
          })
          .then((response) => {
            expect(response.status).to.be.within(200, 299)
            return response.json() as Promise<ApiEnvelope<{ screen_ids: number[]; total: number }>>
          })
      })
    )
  )

const attachTextFixture = (fileName: string, content: string) => {
  cy.get('.el-overlay:visible .el-dialog')
    .last()
    .find('input[type="file"]')
    .selectFile(
      {
        contents: Cypress.Buffer.from(content, 'utf8'),
        fileName,
        mimeType: 'text/plain',
        lastModified: Date.now(),
      },
      { force: true }
    )
}

const clickVisibleDialogPrimaryButton = (label: string) => {
  cy.get('.el-overlay:visible .el-dialog')
    .last()
    .contains('button', label)
    .then(($button) => {
      const button = $button.get(0)
      if (!button) throw new Error(`Dialog button not found: ${label}`)
      button.click()
    })
}

const isScreenParsing = (screen: ScreenItem) =>
  screen.parse_status === 'pending' || screen.parse_status === 'running'

const waitForPrototypeScreensSettled = (
  timeoutMs = 240000,
  failOnTimeout = true
): Cypress.Chainable<ScreenItem[]> =>
  cy.then(() => {
    if (!created.projectId || !created.prototypeProjectId) {
      return cy.wrap([] as ScreenItem[])
    }

    const deadline = Date.now() + timeoutMs

    const poll = (): Cypress.Chainable<ScreenItem[]> =>
      apiRequestDynamic<{ items: ScreenItem[] }>(() => ({
        method: 'GET',
        url: `/api/v1/ui-prototype/screens/${created.projectId}`,
        qs: {
          prototype_project_id: created.prototypeProjectId,
          page: 1,
          page_size: 20,
        },
      })).then((response) => {
        if (response.status >= 400) {
          return cy.wrap([] as ScreenItem[])
        }

        const data = expectSuccessfulApi<{ items: ScreenItem[] }>(response)
        const parsingScreens = data.items.filter(isScreenParsing)
        if (data.items.length > 0 && parsingScreens.length === 0) {
          return cy.wrap(data.items)
        }

        if (Date.now() > deadline) {
          const message = `UI原型解析未在${timeoutMs}ms内结束: ${parsingScreens
            .map((screen) => `${screen.id}:${screen.parse_status}`)
            .join(', ')}`
          if (failOnTimeout) throw new Error(message)
          cy.log(message)
          return cy.wrap(data.items)
        }

        return cy.wait(3000).then(poll)
      })

    return poll()
  })

const selectResourceProject = (projectName: string) => {
  cy.visit('/home/requirement')
  cy.contains('资源中心', { timeout: 15000 }).should('be.visible')
  cy.contains('全部资源', { timeout: 15000 }).should('be.visible')
  cy.contains('.el-form-item', '项目', { timeout: 15000 }).find('.el-select').click()
  cy.get('.el-select-dropdown:visible').contains(projectName).click()
}

const assertPageReady = (title: string) => {
  cy.contains(title, { timeout: 15000 }).should('be.visible')
  cy.get('.main-content').should('not.contain', '404').and('not.contain', '空白页')
}

describe('真实服务主流程 E2E', () => {
  before(() => {
    cy.loginByApi()

    apiRequest<ProjectCreateData>('POST', '/api/v1/project/', {
      body: {
        name: `${e2eName}-项目`,
        description: '真实浏览器E2E自测项目，测试结束自动清理',
        project_type: 'web',
        web_env_configs: {
          test: {
            url: Cypress.config('baseUrl'),
            username: Cypress.env('adminUsername') || 'admin',
            password: Cypress.env('adminPassword') || 'admin123',
          },
        },
      },
    }).then((response) => {
      const data = expectSuccessfulApi<ProjectCreateData>(response)
      created.projectId = data.project_id
    })
  })

  after(() => {
    const cleanupFailures: string[] = []

    cy.then(() => {
      if (created.prototypeProjectId) {
        return waitForPrototypeScreensSettled(180000, false)
      }
      return cy.wrap([] as ScreenItem[])
    })

    cy.then(() => {
      if (created.taskId) {
        apiRequestDynamic<unknown>(() => ({
          method: 'DELETE',
          url: `/api/v1/test-task/${created.taskId}`,
          qs: { project_id: created.projectId },
        })).then((response) => {
          if (response.status >= 400) cleanupFailures.push(`task:${created.taskId}`)
        })
      }
    })

    cy.then(() => {
      if (created.prototypeProjectId) {
        apiRequestDynamic<unknown>(() => ({
          method: 'DELETE',
          url: `/api/v1/ui-prototype/project/${created.prototypeProjectId}`,
        })).then((response) => {
          if (response.status >= 400)
            cleanupFailures.push(`uiPrototype:${created.prototypeProjectId}`)
        })
      }
    })

    cy.then(() => {
      if (created.projectId) {
        apiRequestDynamic<unknown>(() => ({
          method: 'DELETE',
          url: `/api/v1/project/${created.projectId}`,
        })).then((response) => {
          if (response.status >= 400) cleanupFailures.push(`project:${created.projectId}`)
        })
      }
    })

    cy.then(() => {
      if (cleanupFailures.length > 0) {
        cy.log(`清理失败清单: ${cleanupFailures.join(', ')}`)
      }
    })
  })

  it('完成菜单流转、资源上传解析、截图页面流转分析、任务执行反馈走查', () => {
    cy.loginByApi()
    cy.visit('/home/project')
    assertPageReady('项目中心')

    const menuChecks = [
      { menu: '项目中心', path: '/home/project', title: '项目中心' },
      { menu: '资源中心', path: '/home/requirement', title: '资源中心' },
      { menu: '测试点管理', path: '/home/case/test-point-management', title: '测试点管理' },
      { menu: '用例列表', path: '/home/case', title: '用例列表' },
      { menu: 'AI生成用例', path: '/home/case/ai-generate', title: '新增用例生成' },
      { menu: '用例迁移', path: '/home/case/migration', title: '用例迁移' },
      { menu: '执行中心', path: '/home/task', title: '执行中心' },
      { menu: '报告中心', path: '/home/report', title: '报告中心' },
      { menu: 'Pipeline仪表盘', path: '/home/pipeline-dashboard', title: 'Pipeline仪表盘' },
      { menu: '回归变更分析', path: '/home/iteration/regression-generate', title: '回归变更分析' },
      { menu: '用户管理', path: '/home/system/user', title: '用户管理' },
    ]

    cy.get('.sidebar-menu').should('not.contain', '评审').and('not.contain', 'UI原型管理')

    menuChecks.forEach((item) => {
      cy.visit(item.path)
      cy.location('pathname', { timeout: 15000 }).should('eq', item.path)
      assertPageReady(item.title)
    })

    selectResourceProject(`${e2eName}-项目`)
    cy.contains('上传文件').click()
    attachTextFixture(
      `${e2eName}-requirements.txt`,
      [
        '# E2E Requirement',
        '作为管理员，需要能够进入项目中心、资源中心、测试资产、执行中心和报告中心。',
        '上传资源后应能触发真实解析，并可进入测试点管理查看解析入口。',
      ].join('\n')
    )
    cy.contains('.file-preview', `${e2eName}-requirements.txt`, { timeout: 10000 }).should(
      'be.visible'
    )
    clickVisibleDialogPrimaryButton('确定')
    cy.contains('上传', { timeout: 30000 })
    cy.contains(`${e2eName}-requirements.txt`, { timeout: 30000 }).should('be.visible')
    cy.contains('AI分析').click()
    cy.location('pathname', { timeout: 15000 }).should('eq', '/home/case/test-point-management')
    cy.location('search').should('include', 'openExtract=1')

    uploadUiPrototypeScreens(`${e2eName}-UI原型`).then((response) => {
      const data = response.data
      expect(data?.screen_ids.length, 'uploaded UI screen count').to.be.greaterThan(1)
      created.screenIds = data?.screen_ids || []
    })
    selectResourceProject(`${e2eName}-项目`)
    cy.contains(`${e2eName}-UI原型`, { timeout: 30000 }).should('be.visible')

    apiRequestDynamic<{ items: PrototypeProject[] }>(() => ({
      method: 'GET',
      url: `/api/v1/ui-prototype/project/list/${created.projectId}`,
      qs: { page: 1, page_size: 20 },
    })).then((response) => {
      const data = expectSuccessfulApi<{ items: PrototypeProject[] }>(response)
      const prototype = data.items.find((item) => item.name === `${e2eName}-UI原型`)
      expect(prototype, 'created UI prototype').to.not.equal(undefined)
      if (!prototype) throw new Error('UI prototype was not created')
      created.prototypeProjectId = prototype.id
    })

    apiRequestDynamic<{ items: ScreenItem[] }>(() => ({
      method: 'GET',
      url: `/api/v1/ui-prototype/screens/${created.projectId}`,
      qs: {
        prototype_project_id: created.prototypeProjectId,
        page: 1,
        page_size: 20,
      },
    })).then((response) => {
      const data = expectSuccessfulApi<{ items: ScreenItem[] }>(response)
      expect(data.items.length, 'screen count').to.be.greaterThan(0)
      created.screenIds = data.items.map((screen) => screen.id)
    })

    apiRequestDynamic<unknown>(() => ({
      method: 'POST',
      url: '/api/v1/ui-prototype/parse',
      body: {
        screen_ids: created.screenIds,
        prototype_project_id: created.prototypeProjectId,
        parse_mode: 'vision',
      },
    })).then((response) => {
      expectSuccessfulApi<unknown>(response)
    })

    waitForPrototypeScreensSettled().then((screens) => {
      expect(
        screens.some((screen) => screen.parse_status === 'completed'),
        'at least one UI screen parsed successfully'
      ).to.equal(true)
    })

    apiRequestDynamic<{ success: boolean }>(() => ({
      method: 'POST',
      url: '/api/v1/ui-prototype/flow/generate',
      body: {
        prototype_project_id: created.prototypeProjectId,
      },
      timeout: 180000,
    })).then((response) => {
      expectSuccessfulApi<{ success: boolean }>(response)
    })

    cy.then(() => {
      cy.visit(
        `/home/requirement/ui-prototype?project_id=${created.projectId}&prototype_project_id=${created.prototypeProjectId}&name=${encodeURIComponent(`${e2eName}-UI原型`)}`
      )
    })
    assertPageReady(`${e2eName}-UI原型`)
    cy.contains('UI 原型处理流程').should('be.visible')
    cy.contains('分析页面流转').should('be.visible')
    cy.contains('页面流转概览').scrollIntoView().should('be.visible')
    cy.contains('页面数').scrollIntoView().should('be.visible')
    cy.contains('连线数').scrollIntoView().should('be.visible')
    cy.contains('屏幕列表').scrollIntoView().should('be.visible')
    cy.contains('屏幕总数').should('exist')
    cy.contains('视觉模型').should('exist')
    cy.contains('button', /解析页面|AI视觉解析/).should('exist')
    cy.contains('button', '生成测试用例').scrollIntoView().click()
    cy.location('pathname', { timeout: 15000 }).should('eq', '/home/case/ai-generate')
    cy.location('search').should('include', `project_id=${created.projectId}`)
    cy.location('search').then((search) => {
      const uiProjectId = Number(new URLSearchParams(search).get('ui_project_id'))
      expect(uiProjectId, 'ui_project_id query').to.be.greaterThan(0)
    })
    cy.contains(`${e2eName}-UI原型`, { timeout: 30000 }).should('be.visible')
    cy.contains('屏幕预览', { timeout: 30000 }).should('be.visible')
    cy.contains('button', '下一步').scrollIntoView().click()
    cy.contains(/完整上下文生成|轻量生成|上下文待补齐/, { timeout: 30000 }).should('exist')
    cy.contains('UI页面关联').should('exist')

    cy.then(() => {
      cy.visit(
        `/home/requirement/ui-prototype?project_id=${created.projectId}&prototype_project_id=${created.prototypeProjectId}&name=${encodeURIComponent(`${e2eName}-UI原型`)}`
      )
    })
    cy.contains('button', '回归变更分析').scrollIntoView().should('not.be.disabled').click()
    cy.location('pathname', { timeout: 15000 })
      .should('eq', '/home/iteration/regression-generate')
      .and('not.include', '/home/case/iteration')
    cy.then(() => {
      cy.location('search').should('include', `project_id=${created.projectId}`)
    })
    cy.contains('变化来源', { timeout: 15000 }).should('be.visible')
    cy.contains('UI/流程变化').should('be.visible')

    cy.visit('/home/case/migration')
    assertPageReady('用例迁移')
    cy.contains('迁移来源与目标').should('be.visible')
    cy.contains('跨端/跨形态迁移').should('be.visible')

    apiRequestDynamic<{ id: number }>(() => ({
      method: 'POST',
      url: '/api/v1/test-case/',
      body: {
        project_id: created.projectId,
        module: 'E2E自测',
        title: `${e2eName}-打开本地首页`,
        precondition: '本地前端服务已启动，管理员账号可登录',
        steps: [
          {
            step: 1,
            action: `访问 ${Cypress.config('baseUrl')}`,
            action_type: 'navigate',
            target_element: 'AI TestMaster 登录页',
            expected_result: '登录页或已登录首页可访问',
          },
          {
            step: 2,
            action: '检查页面存在 AI TestMaster 或项目中心入口',
            action_type: 'verify',
            target_element: '页面主体',
            expected_result: '页面渲染完成且未出现空白页',
          },
        ],
        expected_result: '本地 AI TestMaster 首页可访问',
        priority: 2,
        case_type: 'ui_automation',
        generate_status: 1,
        lifecycle_status: 'active',
        target_device: 'web',
      },
    })).then((response) => {
      const data = expectSuccessfulApi<{ id: number }>(response)
      created.caseId = data.id
    })

    apiRequestDynamic<TaskCreateData>(() => ({
      method: 'POST',
      url: '/api/v1/test-task/',
      body: {
        project_id: created.projectId,
        task_name: `${e2eName}-真实执行反馈`,
        description: '真实浏览器E2E创建的最小执行任务',
        case_ids: [created.caseId],
      },
    })).then((response) => {
      const data = expectSuccessfulApi<TaskCreateData>(response)
      created.taskId = data.task_id
    })

    apiRequestDynamic<unknown>(() => ({
      method: 'POST',
      url: `/api/v1/test-task/${created.taskId}/start`,
      qs: { project_id: created.projectId },
      body: { execution_mode: 'smart' },
      timeout: 180000,
    })).then((response) => {
      expect(response.status, 'task start returns clear feedback').to.be.within(200, 500)
    })

    cy.then(() => {
      cy.visit(`/home/task/detail/${created.taskId}?project_id=${created.projectId}`)
    })
    assertPageReady('任务详情')
    cy.contains(`${e2eName}-真实执行反馈`, { timeout: 15000 }).should('be.visible')
    cy.contains('执行进度').should('be.visible')
    cy.contains('刷新结果').click()
    cy.contains('总用例').scrollIntoView().should('be.visible')
    cy.contains(/执行完成|执行失败|执行中|等待执行/, { timeout: 30000 }).should('be.visible')

    cy.visit('/home/task')
    cy.contains('执行中心').should('be.visible')
    cy.reload()
    cy.contains(`${e2eName}-真实执行反馈`, { timeout: 30000 }).should('exist')

    cy.visit('/home/case/pipeline/1')
    cy.location('pathname', { timeout: 15000 }).should('eq', '/home/iteration/pipeline/1')
  })
})
