<template>
  <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" @close="handleClose">
    <el-form label-width="96px">
      <el-form-item label="流程类型">
        <el-tag :type="tagType" effect="dark">{{ typeLabel }}</el-tag>
      </el-form-item>

      <el-form-item label="挂靠主干" required>
        <el-select
          v-model="formData.parent_main_node_id"
          placeholder="请选择挂靠的主干页面"
          style="width: 100%"
        >
          <el-option
            v-for="option in mainNodeOptions"
            :key="option.id"
            :label="`${option.main_order || '-'} · ${option.screen_name}`"
            :value="option.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item :label="conditionLabel" required>
        <el-input
          v-model="formData.trigger_condition"
          type="textarea"
          :rows="3"
          :placeholder="conditionPlaceholder"
        />
      </el-form-item>

      <el-form-item v-if="showPreAction" label="前置操作">
        <el-input
          v-model="formData.pre_action"
          type="textarea"
          :rows="2"
          placeholder="例如：点击提交按钮前已填写完整表单"
        />
      </el-form-item>

      <el-form-item v-if="showExpectedResult" label="预期现象">
        <el-input
          v-model="formData.expected_result"
          type="textarea"
          :rows="2"
          :placeholder="expectedResultPlaceholder"
        />
      </el-form-item>

      <el-form-item v-if="showBypassReason" label="跳过原因">
        <el-input
          v-model="formData.bypass_reason"
          type="textarea"
          :rows="2"
          placeholder="例如：已存在有效登录态，直接进入首页"
        />
      </el-form-item>

      <el-form-item label="补充说明">
        <el-input
          v-model="formData.note"
          type="textarea"
          :rows="2"
          placeholder="可补充业务背景、断言重点或恢复方式"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="handleConfirm">确认</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FlowMetaData, FlowNodeData } from '@/store/flowSort'

type NonMainFlowType = Exclude<FlowNodeData['flow_type'], 'main'>

interface MainNodeOption {
  id: string
  screen_id: number
  screen_name: string
  main_order?: number
}

interface FlowTypeConfigForm extends FlowMetaData {
  parent_main_node_id: string
  trigger_condition: string
  pre_action: string
  expected_result: string
  bypass_reason: string
  note: string
}

const props = defineProps<{
  visible: boolean
  flowType: NonMainFlowType
  mainNodeOptions: MainNodeOption[]
  initialData?: Partial<FlowMetaData> | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [data: FlowMetaData]
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const createDefaultFormData = (): FlowTypeConfigForm => ({
  parent_main_node_id: '',
  trigger_condition: '',
  pre_action: '',
  expected_result: '',
  bypass_reason: '',
  note: '',
})

const formData = ref<FlowTypeConfigForm>(createDefaultFormData())

const dialogTitle = computed(() => {
  const titleMap: Record<NonMainFlowType, string> = {
    branch: '配置分支流程',
    exception: '配置异常流程',
    bypass: '配置旁路流程',
  }
  return titleMap[props.flowType]
})

const typeLabel = computed(() => {
  const labelMap: Record<NonMainFlowType, string> = {
    branch: '分支流程',
    exception: '异常流程',
    bypass: '旁路流程',
  }
  return labelMap[props.flowType]
})

const tagType = computed(() => {
  const typeMap: Record<NonMainFlowType, 'success' | 'danger' | 'warning'> = {
    branch: 'success',
    exception: 'danger',
    bypass: 'warning',
  }
  return typeMap[props.flowType]
})

const conditionLabel = computed(() => {
  const labelMap: Record<NonMainFlowType, string> = {
    branch: '触发条件',
    exception: '异常场景',
    bypass: '出现时机',
  }
  return labelMap[props.flowType]
})

const conditionPlaceholder = computed(() => {
  const placeholderMap: Record<NonMainFlowType, string> = {
    branch: '例如：用户点击“更多筛选”按钮后进入高级筛选页',
    exception: '例如：提交时接口超时、鉴权失效、参数校验失败',
    bypass: '例如：进入页面后自动命中快捷入口，跳过中间步骤',
  }
  return placeholderMap[props.flowType]
})

const expectedResultPlaceholder = computed(() => {
  const placeholderMap: Record<NonMainFlowType, string> = {
    branch: '例如：展示高级筛选结果',
    exception: '例如：提示提交失败并允许重试',
    bypass: '例如：直接进入目标页并保留原上下文',
  }
  return placeholderMap[props.flowType]
})

const showPreAction = computed(() => props.flowType === 'exception')
const showExpectedResult = computed(
  () => props.flowType === 'exception' || props.flowType === 'branch'
)
const showBypassReason = computed(() => props.flowType === 'bypass')

watch(
  () => props.visible,
  (val) => {
    if (!val) return
    formData.value = {
      ...createDefaultFormData(),
      ...props.initialData,
      parent_main_node_id: props.initialData?.parent_main_node_id || '',
      trigger_condition: props.initialData?.trigger_condition || '',
      pre_action: props.initialData?.pre_action || '',
      expected_result: props.initialData?.expected_result || '',
      bypass_reason: props.initialData?.bypass_reason || '',
      note: props.initialData?.note || '',
    }
  },
  { immediate: true }
)

const handleClose = () => {
  formData.value = createDefaultFormData()
}

const handleConfirm = () => {
  if (!formData.value.parent_main_node_id) {
    ElMessage.warning('请选择挂靠的主干页面')
    return
  }
  if (!formData.value.trigger_condition.trim()) {
    ElMessage.warning(`请填写${conditionLabel.value}`)
    return
  }

  emit('confirm', {
    parent_main_node_id: formData.value.parent_main_node_id,
    trigger_condition: formData.value.trigger_condition.trim(),
    pre_action: formData.value.pre_action.trim() || undefined,
    expected_result: formData.value.expected_result.trim() || undefined,
    bypass_reason: formData.value.bypass_reason.trim() || undefined,
    note: formData.value.note.trim() || undefined,
  })
}
</script>
