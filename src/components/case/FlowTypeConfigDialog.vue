<template>
  <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" @close="handleClose">
    <el-form label-width="96px">
      <el-form-item label="流程类型">
        <el-tag :type="tagType" effect="dark">{{ typeLabel }}</el-tag>
      </el-form-item>

      <el-form-item label="挂靠节点" required>
        <el-select
          v-model="formData.parent_node_id"
          placeholder="请选择挂靠的父节点（主干或分支）"
          style="width: 100%"
        >
          <el-option-group label="主干节点">
            <el-option
              v-for="option in mainParentOptions"
              :key="option.id"
              :label="`${option.main_order || '-'} · ${option.screen_name}`"
              :value="option.id"
            />
          </el-option-group>
          <el-option-group v-if="branchParentOptions.length > 0" label="分支/异常/弹窗节点">
            <el-option
              v-for="option in branchParentOptions"
              :key="option.id"
              :label="`${indent(option.depth)}${flowTypeTag(option.flow_type)} ${option.screen_name}`"
              :value="option.id"
            />
          </el-option-group>
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

      <el-form-item v-if="showBypassReason" label="出现原因">
        <el-input
          v-model="formData.bypass_reason"
          type="textarea"
          :rows="2"
          placeholder="例如：首次进入页面自动弹出新手引导"
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

interface ParentNodeOption {
  id: string
  screen_id: number
  screen_name: string
  flow_type: NonMainFlowType | 'main'
  main_order?: number
  /** 层级深度，0=主干, 1=一级分支, 2=二级分支... */
  depth: number
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
  mainNodeOptions: ParentNodeOption[]
  initialData?: Partial<FlowMetaData> | null
  /** 当前正在配置的节点 ID，用于排除自身 */
  currentNodeId?: string
  /** 当前节点的子孙 ID 集合，用于排除循环挂靠 */
  excludedNodeIds?: Set<string>
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
  parent_node_id: '',
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
    bypass: '配置弹窗/浮层',
  }
  return titleMap[props.flowType]
})

const typeLabel = computed(() => {
  const labelMap: Record<NonMainFlowType, string> = {
    branch: '分支流程',
    exception: '异常流程',
    bypass: '弹窗/浮层',
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
    bypass: '例如：进入页面后自动弹出公告或新手引导',
  }
  return placeholderMap[props.flowType]
})

const expectedResultPlaceholder = computed(() => {
  const placeholderMap: Record<NonMainFlowType, string> = {
    branch: '例如：展示高级筛选结果',
    exception: '例如：提示提交失败并允许重试',
    bypass: '例如：关闭弹窗后回到当前主流程页面',
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
    const initial = props.initialData || {}
    formData.value = {
      ...createDefaultFormData(),
      ...initial,
      // 兼容旧数据：parent_node_id 为空时回退到 parent_main_node_id
      parent_node_id: initial.parent_node_id || initial.parent_main_node_id || '',
    }
  },
  { immediate: true }
)

const handleClose = () => {
  formData.value = createDefaultFormData()
}

const mainParentOptions = computed(() =>
  props.mainNodeOptions.filter((o) => o.flow_type === 'main')
)

const branchParentOptions = computed(() =>
  props.mainNodeOptions.filter(
    (o) =>
      o.flow_type !== 'main' && o.id !== props.currentNodeId && !props.excludedNodeIds?.has(o.id)
  )
)

const flowTypeTag = (type: NonMainFlowType | 'main'): string => {
  const map: Record<string, string> = {
    main: '[主干]',
    branch: '[分支]',
    exception: '[异常]',
    bypass: '[弹窗]',
  }
  return map[type] || ''
}

const indent = (depth: number): string => '　'.repeat(depth)

const handleConfirm = () => {
  const parentId = formData.value.parent_node_id || formData.value.parent_main_node_id
  if (!parentId) {
    ElMessage.warning('请选择挂靠的父节点')
    return
  }
  if (!formData.value.trigger_condition.trim()) {
    ElMessage.warning(`请填写${conditionLabel.value}`)
    return
  }

  emit('confirm', {
    parent_node_id: parentId,
    parent_main_node_id: parentId,
    trigger_condition: formData.value.trigger_condition.trim(),
    pre_action: formData.value.pre_action.trim() || undefined,
    expected_result: formData.value.expected_result.trim() || undefined,
    bypass_reason: formData.value.bypass_reason.trim() || undefined,
    note: formData.value.note.trim() || undefined,
  })
}
</script>
