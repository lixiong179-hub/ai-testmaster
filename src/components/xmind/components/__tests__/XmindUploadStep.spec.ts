import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { XmindImportKey } from '../../useXmindImport'
import { XMIND_IMPORT_CONFIG } from '@/constants/resource'
import XmindUploadStep from '../XmindUploadStep.vue'

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElSwitchStub = defineComponent({
  name: 'ElSwitch',
  props: { modelValue: { type: Boolean, default: false } },
  emits: ['update:modelValue'],
  template: `<input type="checkbox" class="el-switch" :checked="modelValue" @change="$emit('update:modelValue', $event.target.checked)" />`,
})

const ElProgressStub = defineComponent({
  name: 'ElProgress',
  props: { percentage: { type: Number, default: 0 } },
  template: '<div class="el-progress">{{ percentage }}%</div>',
})

const stubs = {
  ElIcon: ElIconStub,
  ElSwitch: ElSwitchStub,
  ElProgress: ElProgressStub,
}

function fileOf(name: string, size = 1024): File {
  return { name, size } as File
}

function setup(step = 0) {
  const ctx = {
    currentStep: ref(step),
    selectedFile: ref<File | null>(null),
    loading: ref(false),
    aiEnhance: ref(false),
    importProgress: ref<Record<string, unknown> | null>(null),
    importProgressText: ref(''),
    isDragover: ref(false),
    formatFileSize: vi.fn(() => '10 KB'),
  }

  const wrapper = mount(XmindUploadStep, {
    global: {
      stubs,
      provide: { [XmindImportKey as symbol]: ctx },
    },
  })
  return { ctx, wrapper }
}

function selectFile(wrapper: ReturnType<typeof mount>, file: File) {
  const input = wrapper.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
  return input.trigger('change')
}

describe('XmindUploadStep — 渲染', () => {
  beforeEach(() => {
    vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
  })

  it('非上传步骤不渲染内容', () => {
    const { wrapper } = setup(1)

    expect(wrapper.find('.upload-area').exists()).toBe(false)
  })

  it('上传步骤展示格式与大小提示', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.upload-text').text()).toBe('点击或拖拽上传 XMind 文件')
    expect(wrapper.find('.upload-hint').text()).toBe(
      `支持 ${XMIND_IMPORT_CONFIG.ACCEPT} 格式，${XMIND_IMPORT_CONFIG.SIZE_HINT}`
    )
  })

  it('点击拖拽区触发文件选择', async () => {
    const { wrapper } = setup()
    // 真实 click 会冒泡回拖拽区导致递归，这里替换原型方法只做计数
    const clickSpy = vi
      .spyOn(HTMLInputElement.prototype, 'click')
      .mockImplementation(() => undefined)

    await wrapper.find('.upload-drop-zone').trigger('click')

    expect(clickSpy).toHaveBeenCalledTimes(1)
  })

  it('拖拽进入/离开切换高亮', async () => {
    const { ctx, wrapper } = setup()

    await wrapper.find('.upload-drop-zone').trigger('dragover')
    expect(ctx.isDragover.value).toBe(true)
    expect(wrapper.find('.upload-drop-zone').classes()).toContain('is-dragover')

    await wrapper.find('.upload-drop-zone').trigger('dragleave')
    expect(ctx.isDragover.value).toBe(false)
  })
})

describe('XmindUploadStep — 文件校验', () => {
  beforeEach(() => {
    vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
  })

  it('非 .xmind 文件被拒绝', async () => {
    const { ctx, wrapper } = setup()

    await selectFile(wrapper, fileOf('report.pdf'))

    expect(ElMessage.error).toHaveBeenCalledWith('请选择 .xmind 格式的文件')
    expect(ctx.selectedFile.value).toBeNull()
  })

  it('超过大小上限被拒绝', async () => {
    const { ctx, wrapper } = setup()

    await selectFile(wrapper, fileOf('big.xmind', XMIND_IMPORT_CONFIG.MAX_FILE_SIZE + 1))

    expect(ElMessage.error).toHaveBeenCalledWith(XMIND_IMPORT_CONFIG.SIZE_HINT)
    expect(ctx.selectedFile.value).toBeNull()
  })

  it('合法文件写入选中态并展示文件名与大小', async () => {
    const { ctx, wrapper } = setup()

    await selectFile(wrapper, fileOf('用例.xmind', 2048))

    expect(ctx.selectedFile.value).toMatchObject({ name: '用例.xmind' })
    expect(wrapper.find('.file-name').text()).toBe('用例.xmind')
    expect(wrapper.find('.file-size').text()).toBe('10 KB')
    expect(ctx.formatFileSize).toHaveBeenCalledWith(2048)
  })

  it('拖拽投放合法文件生效，投放结束取消高亮', async () => {
    const { ctx, wrapper } = setup()
    ctx.isDragover.value = true

    await wrapper.find('.upload-drop-zone').trigger('drop', {
      dataTransfer: { files: [fileOf('拖拽.xmind', 100)] },
    })

    expect(ctx.selectedFile.value).toMatchObject({ name: '拖拽.xmind' })
    expect(ctx.isDragover.value).toBe(false)
  })

  it('拖拽投放非法文件被忽略', async () => {
    const { ctx, wrapper } = setup()

    await wrapper.find('.upload-drop-zone').trigger('drop', {
      dataTransfer: { files: [fileOf('恶意.exe', 100)] },
    })

    expect(ElMessage.error).toHaveBeenCalledWith('请选择 .xmind 格式的文件')
    expect(ctx.selectedFile.value).toBeNull()
  })

  it('清除按钮移除已选文件', async () => {
    const { ctx, wrapper } = setup()
    ctx.selectedFile.value = fileOf('用例.xmind')
    await wrapper.vm.$nextTick()

    await wrapper.find('.file-remove').trigger('click')

    expect(ctx.selectedFile.value).toBeNull()
    expect(wrapper.find('.file-info').exists()).toBe(false)
  })
})

describe('XmindUploadStep — 进度与增强开关', () => {
  it('仅 AI 增强且加载中展示进度文案', async () => {
    const { ctx, wrapper } = setup()

    expect(wrapper.find('.import-progress-area').exists()).toBe(false)

    ctx.loading.value = true
    ctx.aiEnhance.value = true
    ctx.importProgressText.value = '正在解析第 1 批'
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.import-progress-text').text()).toBe('正在解析第 1 批')
  })

  it('多批次时渲染进度条', async () => {
    const { ctx, wrapper } = setup()
    ctx.loading.value = true
    ctx.aiEnhance.value = true
    ctx.importProgressText.value = '解析中'
    ctx.importProgress.value = { total_batches: 3, completed_batches: 1, percentage: 33 }
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.el-progress').text()).toBe('33%')
  })

  it('AI 增强开关双向绑定', async () => {
    const { ctx, wrapper } = setup()

    await wrapper.find('.el-switch').setValue(true)

    expect(ctx.aiEnhance.value).toBe(true)
  })
})
