import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { ElMessage } from 'element-plus'

vi.mock('@/api/file', () => ({
  fileApi: { batchUploadFiles: vi.fn() },
}))

vi.mock('@/api/uiPrototype', () => ({
  uiPrototypeApi: { uploadUIScreens: vi.fn() },
}))

import { fileApi } from '@/api/file'
import { uiPrototypeApi } from '@/api/uiPrototype'
import { detectResourceType, getResourceTypeLabel } from '@/constants/resource'
import RequirementUploader from '../RequirementUploader.vue'

const batchUploadMock = vi.mocked(fileApi.batchUploadFiles)
const uploadScreensMock = vi.mocked(uiPrototypeApi.uploadUIScreens)

const ElUploadStub = defineComponent({
  name: 'ElUpload',
  props: {
    onChange: { type: Function, default: undefined },
    onExceed: { type: Function, default: undefined },
    limit: { type: Number, default: 0 },
    accept: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
  },
  methods: {
    clearFiles() {
      /* 模拟 el-upload 实例方法 */
    },
  },
  template: '<div class="el-upload"><slot /><slot name="tip" /></div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: `<button class="el-button" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: { modelValue: { type: String, default: '' }, placeholder: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<input class="el-input" :value="modelValue" :placeholder="placeholder" @input="$emit('update:modelValue', $event.target.value)" />`,
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<select class="el-select" :value="modelValue" @change="$emit('update:modelValue', $event.target.value)"><slot /></select>`,
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: String, default: '' } },
  template: '<option class="el-option" :value="value">{{ label }}</option>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  template: '<span class="el-tag"><slot /></span>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

function fileOf(name: string, size = 1024): File {
  return { name, size } as File
}

function uploadFilesOf(...files: File[]) {
  return files.map((raw, index) => ({ uid: index + 1, name: raw.name, raw }))
}

function mountUploader(props: Record<string, unknown> = {}) {
  return mount(RequirementUploader, {
    props: { projectId: 7, ...props },
    global: {
      stubs: {
        ElUpload: ElUploadStub,
        ElButton: ElButtonStub,
        ElInput: ElInputStub,
        ElSelect: ElSelectStub,
        ElOption: ElOptionStub,
        ElTag: ElTagStub,
        ElIcon: ElIconStub,
      },
    },
  })
}

async function selectFiles(wrapper: ReturnType<typeof mountUploader>, ...files: File[]) {
  const upload = wrapper.findComponent(ElUploadStub)
  const onChange = upload.props('onChange') as (f: unknown, files: unknown[]) => void
  onChange(uploadFilesOf(...files)[0], uploadFilesOf(...files))
  await wrapper.vm.$nextTick()
}

describe('RequirementUploader — 文件预览', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(ElMessage, 'warning').mockImplementation(() => undefined as never)
    vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
    vi.spyOn(ElMessage, 'success').mockImplementation(() => undefined as never)
  })

  it('未选文件时不渲染预览与上传按钮', () => {
    const wrapper = mountUploader()

    expect(wrapper.find('.file-preview').exists()).toBe(false)
    expect(wrapper.find('.upload-actions').exists()).toBe(false)
    expect(wrapper.find('.el-upload__tip').text()).toContain('最多20个文件')
  })

  it('选择文件后展示名称、大小与自动识别的类型', async () => {
    const wrapper = mountUploader()

    await selectFiles(wrapper, fileOf('需求说明.docx', 2048))

    expect(wrapper.findAll('.preview-item')).toHaveLength(1)
    expect(wrapper.find('.file-name').text()).toBe('需求说明.docx')
    expect(wrapper.find('.file-size').text()).toBe('2.0 KB')
    expect(wrapper.find('.el-tag').text()).toBe(
      getResourceTypeLabel(detectResourceType('需求说明.docx'))
    )
  })

  it('文件大小格式化覆盖 B/KB/MB 三档', async () => {
    const wrapper = mountUploader()

    await selectFiles(
      wrapper,
      fileOf('a.txt', 512),
      fileOf('b.txt', 1024),
      fileOf('c.txt', 1572864)
    )

    expect(wrapper.findAll('.file-size').map((s) => s.text())).toEqual([
      '512 B',
      '1.0 KB',
      '1.5 MB',
    ])
  })

  it('全部为图片时显示资源名称输入并默认取首个文件名', async () => {
    const wrapper = mountUploader()

    await selectFiles(wrapper, fileOf('登录页原型.png', 100), fileOf('首页原型.jpg', 100))

    expect(wrapper.find('.resource-name-input').exists()).toBe(true)
    expect((wrapper.find('.resource-name-input .el-input').element as HTMLInputElement).value).toBe(
      '登录页原型'
    )
  })

  it('混合文件类型时不显示资源名称输入', async () => {
    const wrapper = mountUploader()

    await selectFiles(wrapper, fileOf('登录页.png', 100), fileOf('需求.docx', 100))

    expect(wrapper.find('.resource-name-input').exists()).toBe(false)
  })

  it('全局类型覆盖同步到所有预览项', async () => {
    const wrapper = mountUploader()
    await selectFiles(wrapper, fileOf('需求.docx', 100))

    await wrapper.find('.el-select').setValue('ui_mockup')

    expect(wrapper.find('.el-tag').text()).toBe(getResourceTypeLabel('ui_mockup'))
  })

  it('清空文件重置预览与类型选择', async () => {
    const wrapper = mountUploader()
    await selectFiles(wrapper, fileOf('需求.docx', 100))
    await wrapper.find('.el-select').setValue('ui_mockup')

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '清空文件')!
      .trigger('click')

    expect(wrapper.find('.file-preview').exists()).toBe(false)
    expect(wrapper.find('.global-override').exists()).toBe(false)
    expect(wrapper.vm.fileCount).toBe(0)
  })

  it('超过数量限制时提示上限', async () => {
    const wrapper = mountUploader({ limit: 3 })
    const upload = wrapper.findComponent(ElUploadStub)

    ;(upload.props('onExceed') as () => void)()

    expect(ElMessage.warning).toHaveBeenCalledWith('最多上传 3 个文件')
  })
})

describe('RequirementUploader — 上传', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(ElMessage, 'warning').mockImplementation(() => undefined as never)
    vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
    vi.spyOn(ElMessage, 'success').mockImplementation(() => undefined as never)
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
  })

  it('未选项目时拦截', async () => {
    const wrapper = mountUploader({ projectId: '' })

    await wrapper.vm.upload()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
  })

  it('未选文件时拦截', async () => {
    const wrapper = mountUploader()

    await wrapper.vm.upload()

    expect(ElMessage.warning).toHaveBeenCalledWith('请选择文件')
    expect(batchUploadMock).not.toHaveBeenCalled()
  })

  it('非图片文件走批量上传并携带描述与迭代ID', async () => {
    batchUploadMock.mockResolvedValue({
      data: { success_count: 2, fail_count: 0 },
    } as never)
    const wrapper = mountUploader({ description: '需求文档', iterationId: 5 })
    await selectFiles(wrapper, fileOf('需求.docx', 100), fileOf('说明.pdf', 100))

    await wrapper.vm.upload()

    expect(batchUploadMock).toHaveBeenCalledWith(
      7,
      [
        expect.objectContaining({ name: '需求.docx' }),
        expect.objectContaining({ name: '说明.pdf' }),
      ],
      'other',
      '需求文档',
      '',
      5
    )
    expect(ElMessage.success).toHaveBeenCalledWith('成功上传 2 个文件')
    expect(wrapper.emitted('success')).toHaveLength(1)
    expect(wrapper.vm.fileCount).toBe(0)
  })

  it('部分失败时给出成功/失败数量', async () => {
    batchUploadMock.mockResolvedValue({
      data: { success_count: 1, fail_count: 2 },
    } as never)
    const wrapper = mountUploader()
    await selectFiles(wrapper, fileOf('a.docx', 100))

    await wrapper.vm.upload()

    expect(ElMessage.warning).toHaveBeenCalledWith('上传完成：成功 1 个，失败 2 个')
  })

  it('迭代ID 为负数或未设置时不传该参数', async () => {
    batchUploadMock.mockResolvedValue({ data: { success_count: 1, fail_count: 0 } } as never)
    const wrapper = mountUploader({ iterationId: -1 })
    await selectFiles(wrapper, fileOf('a.docx', 100))

    await wrapper.vm.upload()

    expect(batchUploadMock.mock.calls[0][5]).toBeUndefined()
  })

  it('全图片走 UI 原型上传并复用资源名称', async () => {
    uploadScreensMock.mockResolvedValue({ data: { total: 2 } } as never)
    const wrapper = mountUploader()
    await selectFiles(wrapper, fileOf('登录页原型.png', 100), fileOf('首页原型.png', 100))

    await wrapper.vm.upload()

    expect(uploadScreensMock).toHaveBeenCalledWith(
      7,
      [
        expect.objectContaining({ name: '登录页原型.png' }),
        expect.objectContaining({ name: '首页原型.png' }),
      ],
      '登录页原型',
      undefined,
      undefined
    )
    expect(ElMessage.success).toHaveBeenCalledWith('成功创建UI原型项目，包含 2 张图片')
    expect(batchUploadMock).not.toHaveBeenCalled()
  })

  it('上传异常时提示并抛出 error 事件', async () => {
    batchUploadMock.mockRejectedValue(new Error('network'))
    const wrapper = mountUploader()
    await selectFiles(wrapper, fileOf('a.docx', 100))

    const result = await wrapper.vm.upload()

    expect(result).toBeNull()
    expect(ElMessage.error).toHaveBeenCalledWith('批量上传失败')
    expect(wrapper.emitted('error')).toHaveLength(1)
    expect(wrapper.vm.uploading).toBe(false)
  })

  it('隐藏上传按钮时不渲染操作区', async () => {
    const wrapper = mountUploader({ showUploadButton: false })
    await selectFiles(wrapper, fileOf('a.docx', 100))

    expect(wrapper.find('.upload-actions').exists()).toBe(false)
  })
})
