import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  submitCard: vi.fn(),
  resetCard: vi.fn(),
  clearError: vi.fn(),
  isRunning: false,
  fields: {} as Record<string, { value: unknown }>,
}))

vi.mock('@/views/project/useQuickTestEntry', async () => {
  const { ref } = await import('vue')
  mocks.fields.url = ref('')
  mocks.fields.description = ref('')
  mocks.fields.username = ref('')
  mocks.fields.password = ref('')
  mocks.fields.error = ref('')
  mocks.fields.loading = ref(false)
  return {
    useQuickTestCard: () => ({
      ...mocks.fields,
      submitCard: mocks.submitCard,
      resetCard: mocks.resetCard,
      clearError: mocks.clearError,
    }),
  }
})

vi.mock('@/store/quickTest', () => ({
  useQuickTestStore: () => ({
    get isRunning() {
      return mocks.isRunning
    },
  }),
}))

import QuickInputCard from '../QuickInputCard.vue'

type Fields = {
  url: { value: string }
  description: { value: string }
  username: { value: string }
  password: { value: string }
  error: { value: string }
  loading: { value: boolean }
}

function fields() {
  return mocks.fields as unknown as Fields
}

async function mountCard(props: Record<string, unknown> = {}) {
  const wrapper = mount(QuickInputCard, { props })
  await flushPromises()
  return wrapper
}

function submitButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('.el-button').find((node) => node.text().includes('开始测试'))!
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.isRunning = false
  fields().url.value = ''
  fields().description.value = ''
  fields().username.value = ''
  fields().password.value = ''
  fields().error.value = ''
  fields().loading.value = false
})

describe('QuickInputCard — URL 回填', () => {
  it('挂载时回填默认 URL', async () => {
    await mountCard({ defaultUrl: 'https://example.com' })

    expect(fields().url.value).toBe('https://example.com')
  })

  it('已有输入时不覆盖', async () => {
    fields().url.value = 'https://typed.com'

    await mountCard({ defaultUrl: 'https://example.com' })

    expect(fields().url.value).toBe('https://typed.com')
  })

  it('defaultUrl 变化时若输入为空则回填', async () => {
    const wrapper = await mountCard()

    await wrapper.setProps({ defaultUrl: 'https://rerun.com' })
    await flushPromises()

    expect(fields().url.value).toBe('https://rerun.com')
  })
})

describe('QuickInputCard — 提交', () => {
  it('提交成功（store 进入 running）后通知父组件', async () => {
    mocks.submitCard.mockImplementation(async () => {
      mocks.isRunning = true
    })
    const wrapper = await mountCard()

    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(mocks.submitCard).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('launched')).toHaveLength(1)
  })

  it('未进入 running 时不通知父组件', async () => {
    mocks.submitCard.mockResolvedValue(undefined)
    const wrapper = await mountCard()

    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.emitted('launched')).toBeUndefined()
  })

  it('回车同样触发提交', async () => {
    mocks.submitCard.mockResolvedValue(undefined)
    const wrapper = await mountCard()

    await wrapper.find('.quick-input-url input').trigger('keyup.enter')
    await flushPromises()

    expect(mocks.submitCard).toHaveBeenCalledTimes(1)
  })

  it('提交中按钮进入 loading 态', async () => {
    fields().loading.value = true
    const wrapper = await mountCard()

    expect(submitButton(wrapper).classes()).toContain('is-loading')
  })
})

describe('QuickInputCard — 错误与重置', () => {
  it('渲染内联错误并在输入时清除', async () => {
    fields().error.value = '请输入网址'
    const wrapper = await mountCard()

    expect(wrapper.find('.quick-input-error').text()).toBe('请输入网址')

    wrapper.findAllComponents({ name: 'ElInput' })[0].vm.$emit('input', 'https://a.com')
    await flushPromises()

    expect(mocks.clearError).toHaveBeenCalledTimes(1)
  })

  it('点击重置调用 resetCard', async () => {
    const wrapper = await mountCard()

    const resetBtn = wrapper.findAll('.el-button').find((node) => node.text() === '重置')!
    await resetBtn.trigger('click')

    expect(mocks.resetCard).toHaveBeenCalledTimes(1)
  })

  it('高级选项默认收起', async () => {
    const wrapper = await mountCard()

    expect(wrapper.findComponent({ name: 'ElCollapse' }).props('modelValue')).toEqual([])
  })
})
