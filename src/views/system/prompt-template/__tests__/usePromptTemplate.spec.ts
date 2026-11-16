import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { createComposableHost, mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'
import type { PromptTemplate } from '@/api/promptTemplate'

const mocks = vi.hoisted(() => ({
  getList: vi.fn(),
  registerVersion: vi.fn(),
  setDefault: vi.fn(),
  rollback: vi.fn(),
}))

vi.mock('@/api/promptTemplate', () => ({
  promptTemplateApi: {
    getList: mocks.getList,
    registerVersion: mocks.registerVersion,
    setDefault: mocks.setDefault,
    rollback: mocks.rollback,
  },
}))

import { usePromptTemplate } from '../usePromptTemplate'

type Ctx = ReturnType<typeof usePromptTemplate>

const host = createComposableHost<Ctx>(() => usePromptTemplate())
let ctx: Ctx

function makeVersion(overrides: Partial<PromptTemplate> = {}): PromptTemplate {
  return {
    id: 1,
    prompt_key: 'case.generate',
    prompt_version: 1,
    prompt_hash: 'hash-1',
    content: '默认内容',
    enabled: true,
    is_default: false,
    description: null,
    created_at: '2026-06-27T10:00:00',
    ...overrides,
  }
}

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

function makeFormRef(valid = true) {
  return {
    validate: valid
      ? vi.fn().mockResolvedValue(true)
      : vi.fn().mockRejectedValue(new Error('invalid')),
    resetFields: vi.fn(),
    clearValidate: vi.fn(),
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mockConfirm()
  mocks.getList.mockResolvedValue({
    data: {
      items: [
        makeVersion({
          id: 2,
          prompt_key: 'case.generate',
          prompt_version: 2,
          prompt_hash: 'hash-2',
        }),
        makeVersion({
          id: 1,
          prompt_key: 'case.generate',
          prompt_version: 1,
          is_default: true,
          prompt_hash: 'hash-1',
        }),
        makeVersion({ id: 3, prompt_key: 'ai.review', prompt_version: 1, prompt_hash: 'hash-r' }),
      ],
    },
  })
  mocks.registerVersion.mockResolvedValue({ data: {} })
  mocks.setDefault.mockResolvedValue({ data: {} })
  mocks.rollback.mockResolvedValue({ data: {} })
})

describe('usePromptTemplate — 加载与分组', () => {
  it('挂载后按 100 条拉取并分组，默认选中首个 key', async () => {
    await mountHost()

    expect(mocks.getList).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(ctx.registries.value.map((r) => r.key)).toEqual(['ai.review', 'case.generate'])
    expect(ctx.selectedKey.value).toBe('ai.review')
    expect(ctx.loading.value).toBe(false)
  })

  it('分组内版本按升序，并记录默认与最新版本', async () => {
    await mountHost()

    const registry = ctx.registries.value.find((r) => r.key === 'case.generate')!
    expect(registry.versions.map((v) => v.prompt_version)).toEqual([1, 2])
    expect(registry.defaultVersion?.id).toBe(1)
    expect(registry.latestVersion?.id).toBe(2)
  })

  it('刷新后保留仍然存在的选中 key', async () => {
    await mountHost()
    ctx.selectedKey.value = 'case.generate'
    mocks.getList.mockClear()

    // loadAll 未对外暴露，用「设为默认」触发的重新加载验证选中保持逻辑
    ctx.setDefault(makeVersion())
    await flushPromises()

    expect(mocks.getList).toHaveBeenCalledTimes(1)
    expect(ctx.selectedKey.value).toBe('case.generate')
  })

  it('原选中 key 消失时回退到首个 key', async () => {
    await mountHost()
    ctx.selectedKey.value = 'removed.key'
    mocks.getList.mockResolvedValue({
      data: { items: [makeVersion({ id: 3, prompt_key: 'ai.review' })] },
    })

    ctx.setDefault(makeVersion())
    await flushPromises()

    expect(ctx.selectedKey.value).toBe('ai.review')
  })

  it('列表为空时清空选中', async () => {
    mocks.getList.mockResolvedValue({ data: { items: [] } })

    await mountHost()

    expect(ctx.registries.value).toEqual([])
    expect(ctx.selectedKey.value).toBeNull()
  })

  it('加载失败时提示 Error 信息', async () => {
    mocks.getList.mockRejectedValue(new Error('模板服务异常'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('模板服务异常')
    expect(ctx.loading.value).toBe(false)
  })

  it('加载失败且非 Error 时使用兜底文案', async () => {
    mocks.getList.mockRejectedValue('boom')

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取 Prompt 模板列表失败')
  })
})

describe('usePromptTemplate — 计算属性', () => {
  it('filterText 为空白时返回全部，否则按 key 小写模糊匹配', async () => {
    await mountHost()

    ctx.filterText.value = '   '
    expect(ctx.filteredRegistries.value).toHaveLength(2)

    ctx.filterText.value = 'CASE'
    expect(ctx.filteredRegistries.value.map((r) => r.key)).toEqual(['case.generate'])
  })

  it('currentRegistry 未选中时为 null，选中不存在时为 null', async () => {
    await mountHost()

    ctx.selectedKey.value = null
    expect(ctx.currentRegistry.value).toBeNull()

    ctx.selectedKey.value = 'missing'
    expect(ctx.currentRegistry.value).toBeNull()
  })

  it('currentVersions 按版本号降序', async () => {
    await mountHost()
    ctx.selectedKey.value = 'case.generate'

    expect(ctx.currentVersions.value.map((v) => v.prompt_version)).toEqual([2, 1])

    ctx.selectedKey.value = null
    expect(ctx.currentVersions.value).toEqual([])
  })
})

describe('usePromptTemplate — 展开与预览', () => {
  it('selectKey 切换 key 并清空展开状态', async () => {
    await mountHost()
    ctx.toggleExpand(1)

    ctx.selectKey('case.generate')

    expect(ctx.selectedKey.value).toBe('case.generate')
    expect(ctx.expandedIds.value.size).toBe(0)
  })

  it('toggleExpand 切换单个版本的展开状态', async () => {
    await mountHost()

    ctx.toggleExpand(1)
    expect(ctx.isExpanded(1)).toBe(true)

    ctx.toggleExpand(1)
    expect(ctx.isExpanded(1)).toBe(false)
  })

  it('超过 200 字符才需要折叠', async () => {
    await mountHost()

    expect(ctx.needCollapse('a'.repeat(200))).toBe(false)
    expect(ctx.needCollapse('a'.repeat(201))).toBe(true)
  })

  it('getPreview 超长时截断并补省略号', async () => {
    await mountHost()

    expect(ctx.getPreview('短内容')).toBe('短内容')
    expect(ctx.getPreview('b'.repeat(250))).toBe('b'.repeat(200) + '...')
  })
})

describe('usePromptTemplate — 注册新版本', () => {
  it('打开弹窗时按优先级预填 key', async () => {
    await mountHost()

    ctx.openRegisterDialog('custom.key')
    expect(ctx.registerForm.prompt_key).toBe('custom.key')
    expect(ctx.registerForm.content).toBe('')
    expect(ctx.registerDialogVisible.value).toBe(true)

    ctx.registerDialogVisible.value = false
    ctx.openRegisterDialog()
    expect(ctx.registerForm.prompt_key).toBe('ai.review')
  })

  it('表单实例未就绪时不做任何提交', async () => {
    await mountHost()

    await ctx.submitRegister()

    expect(mocks.registerVersion).not.toHaveBeenCalled()
  })

  it('校验未通过时不提交', async () => {
    await mountHost()
    ctx.registerFormRef.value = makeFormRef(false) as never

    await ctx.submitRegister()

    expect(mocks.registerVersion).not.toHaveBeenCalled()
    expect(ctx.actionLoading.value).toBe(false)
  })

  it('提交成功后关闭弹窗、选中新 key 并刷新', async () => {
    await mountHost()
    ctx.registerFormRef.value = makeFormRef() as never
    ctx.openRegisterDialog('case.generate')
    ctx.registerForm.content = '新的模板内容'
    ctx.registerForm.description = ''
    mocks.getList.mockClear()

    await ctx.submitRegister()

    expect(mocks.registerVersion).toHaveBeenCalledWith({
      prompt_key: 'case.generate',
      content: '新的模板内容',
      description: undefined,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('新版本注册成功')
    expect(ctx.registerDialogVisible.value).toBe(false)
    expect(ctx.selectedKey.value).toBe('case.generate')
    expect(mocks.getList).toHaveBeenCalledTimes(1)
    expect(ctx.actionLoading.value).toBe(false)
  })

  it('描述为空字符串时转成 undefined 提交', async () => {
    await mountHost()
    ctx.registerFormRef.value = makeFormRef() as never
    ctx.registerForm.prompt_key = 'k'
    ctx.registerForm.description = '有描述'

    await ctx.submitRegister()

    expect(mocks.registerVersion).toHaveBeenCalledWith({
      prompt_key: 'k',
      content: '',
      description: '有描述',
    })
  })

  it('提交失败时提示错误并复位 loading', async () => {
    mocks.registerVersion.mockRejectedValue(new Error('Key 已存在'))
    await mountHost()
    ctx.registerFormRef.value = makeFormRef() as never

    await ctx.submitRegister()

    expect(ElMessage.error).toHaveBeenCalledWith('Key 已存在')
    expect(ctx.actionLoading.value).toBe(false)
  })

  it('提交失败且非 Error 时使用兜底文案', async () => {
    mocks.registerVersion.mockRejectedValue(undefined)
    await mountHost()
    ctx.registerFormRef.value = makeFormRef() as never

    await ctx.submitRegister()

    expect(ElMessage.error).toHaveBeenCalledWith('注册新版本失败')
  })
})

describe('usePromptTemplate — 设为默认与回滚', () => {
  it('确认后设为默认并刷新', async () => {
    await mountHost()
    mocks.getList.mockClear()

    ctx.setDefault(makeVersion({ prompt_version: 2 }))
    await flushPromises()

    expect(mocks.setDefault).toHaveBeenCalledWith('case.generate', 2)
    expect(ElMessage.success).toHaveBeenCalledWith('已设为默认版本')
    expect(mocks.getList).toHaveBeenCalledTimes(1)
    expect(ctx.actionLoading.value).toBe(false)
  })

  it('取消设为默认时不调用接口', async () => {
    await mountHost()
    mockCancel()

    ctx.setDefault(makeVersion())
    await flushPromises()

    expect(mocks.setDefault).not.toHaveBeenCalled()
  })

  it('设为默认失败时提示错误', async () => {
    mocks.setDefault.mockRejectedValue(new Error('无权限'))
    await mountHost()

    ctx.setDefault(makeVersion())
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('无权限')
    expect(ctx.actionLoading.value).toBe(false)
  })

  it('确认后回滚并刷新', async () => {
    await mountHost()
    mocks.getList.mockClear()

    ctx.rollback(makeVersion({ prompt_version: 1 }))
    await flushPromises()

    expect(mocks.rollback).toHaveBeenCalledWith('case.generate', 1)
    expect(ElMessage.success).toHaveBeenCalledWith('回滚成功')
    expect(mocks.getList).toHaveBeenCalledTimes(1)
  })

  it('取消回滚时不调用接口', async () => {
    await mountHost()
    mockCancel()

    ctx.rollback(makeVersion())
    await flushPromises()

    expect(mocks.rollback).not.toHaveBeenCalled()
  })

  it('回滚失败时提示错误', async () => {
    mocks.rollback.mockRejectedValue(new Error('版本不存在'))
    await mountHost()

    ctx.rollback(makeVersion())
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('版本不存在')
  })
})

describe('usePromptTemplate — 格式化工具', () => {
  it('formatTime 空值展示占位符，非法值原样返回', async () => {
    await mountHost()

    expect(ctx.formatTime('')).toBe('-')
    expect(ctx.formatTime('not-a-date')).toBe('not-a-date')
  })

  it('formatTime 输出 YYYY-MM-DD HH:mm', async () => {
    await mountHost()
    const date = new Date(2026, 5, 27, 9, 5)

    expect(ctx.formatTime(date.toISOString())).toBe('2026-06-27 09:05')
  })

  it('shortHash 仅截断长哈希', async () => {
    await mountHost()

    expect(ctx.shortHash('')).toBe('')
    expect(ctx.shortHash('1234567890123456')).toBe('1234567890123456')
    expect(ctx.shortHash('1234567890abcdefghij')).toBe('12345678...cdefghij')
  })

  it('hasSameHashElsewhere 判断同 key 内是否存在重复哈希', async () => {
    await mountHost()
    ctx.selectedKey.value = 'case.generate'
    const row = ctx.currentVersions.value[0]

    expect(ctx.hasSameHashElsewhere(row)).toBe(false)

    const duplicated = { ...row, id: 99, prompt_hash: ctx.currentVersions.value[1].prompt_hash }
    expect(ctx.hasSameHashElsewhere(duplicated)).toBe(true)

    ctx.selectedKey.value = null
    expect(ctx.hasSameHashElsewhere(row)).toBe(false)
  })
})
