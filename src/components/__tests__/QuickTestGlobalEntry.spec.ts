import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

const entry = vi.hoisted(() => ({
  launchByUrl: vi.fn(),
  validateUrl: vi.fn(),
  loading: { value: false } as { value: boolean },
}))

vi.mock('@/views/project/useQuickTestEntry', async () => {
  const { ref } = await import('vue')
  entry.loading = ref(false)
  return {
    useQuickTestEntry: () => ({
      loading: entry.loading,
      validateUrl: entry.validateUrl,
      launchByUrl: entry.launchByUrl,
    }),
  }
})

import QuickTestGlobalEntry from '../QuickTestGlobalEntry.vue'

const ElPopoverStub = defineComponent({
  name: 'ElPopover',
  props: { visible: { type: Boolean, default: false } },
  emits: ['update:visible'],
  setup(props, { slots }) {
    return () =>
      h('div', { class: 'el-popover' }, [
        h('div', { class: 'popover-reference' }, slots.reference?.()),
        props.visible ? h('div', { class: 'popover-body' }, slots.default?.()) : null,
      ])
  },
})

const stubs = { ElPopover: ElPopoverStub }

async function openPopover(wrapper: VueWrapper) {
  wrapper.findComponent({ name: 'ElPopover' }).vm.$emit('update:visible', true)
  await flushPromises()
}

async function mountEntry(options: { visible?: boolean } = {}) {
  entry.loading.value = false
  entry.validateUrl.mockReturnValue(null)
  entry.launchByUrl.mockResolvedValue(true)
  const wrapper = mount(QuickTestGlobalEntry, { global: { stubs } })
  if (options.visible) await openPopover(wrapper)
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('QuickTestGlobalEntry — 入口', () => {
  it('渲染带无障碍属性的入口按钮', async () => {
    const wrapper = await mountEntry()

    const btn = wrapper.find('.quick-global-entry')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('title')).toBe('快速测试')
    expect(btn.attributes('aria-label')).toBe('快速测试')
    expect(wrapper.text()).toContain('快速测试')
  })

  it('浮层收起时不渲染表单', async () => {
    const wrapper = await mountEntry()

    expect(wrapper.find('.popover-body').exists()).toBe(false)
  })
})

describe('QuickTestGlobalEntry — 启动校验', () => {
  it('URL 非法时展示内联错误且不发起启动', async () => {
    const wrapper = await mountEntry({ visible: true })
    entry.validateUrl.mockReturnValue('网址必须以 http:// 或 https:// 开头')

    await wrapper.find('.quick-popover-submit').trigger('click')
    await flushPromises()

    expect(wrapper.find('.quick-popover-error').text()).toBe('网址必须以 http:// 或 https:// 开头')
    expect(entry.launchByUrl).not.toHaveBeenCalled()
  })

  it('启动成功后关闭浮层', async () => {
    const wrapper = await mountEntry({ visible: true })
    await wrapper.find('.quick-popover-input input').setValue('https://example.com')

    await wrapper.find('.quick-popover-submit').trigger('click')
    await flushPromises()

    expect(entry.launchByUrl).toHaveBeenCalledWith('https://example.com')
    expect(wrapper.find('.popover-body').exists()).toBe(false)
  })

  it('启动失败时保持浮层打开', async () => {
    const wrapper = await mountEntry({ visible: true })
    entry.launchByUrl.mockResolvedValue(false)

    await wrapper.find('.quick-popover-submit').trigger('click')
    await flushPromises()

    expect(wrapper.find('.popover-body').exists()).toBe(true)
  })

  it('回车触发启动', async () => {
    const wrapper = await mountEntry({ visible: true })

    await wrapper.find('.quick-popover-input input').trigger('keyup.enter')
    await flushPromises()

    expect(entry.launchByUrl).toHaveBeenCalledTimes(1)
  })

  it('输入时清除内联错误', async () => {
    const wrapper = await mountEntry({ visible: true })
    entry.validateUrl.mockReturnValue('请输入网址')
    await wrapper.find('.quick-popover-submit').trigger('click')
    await flushPromises()
    expect(wrapper.find('.quick-popover-error').exists()).toBe(true)

    wrapper.findAllComponents({ name: 'ElInput' })[0].vm.$emit('input', 'https://a.com')
    await flushPromises()

    expect(wrapper.find('.quick-popover-error').exists()).toBe(false)
  })

  it('关闭浮层后清空残留错误', async () => {
    const wrapper = await mountEntry({ visible: true })
    entry.validateUrl.mockReturnValue('请输入网址')
    await wrapper.find('.quick-popover-submit').trigger('click')
    await flushPromises()

    wrapper.findComponent({ name: 'ElPopover' }).vm.$emit('update:visible', false)
    await flushPromises()
    await openPopover(wrapper)

    expect(wrapper.find('.quick-popover-error').exists()).toBe(false)
  })

  it('提交中按钮进入 loading 态', async () => {
    const wrapper = await mountEntry({ visible: true })
    entry.loading.value = true
    await flushPromises()

    expect(wrapper.find('.quick-popover-submit').classes()).toContain('is-loading')
  })
})
