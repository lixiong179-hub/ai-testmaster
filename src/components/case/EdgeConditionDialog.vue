<template>
  <el-dialog v-model="dialogVisible" title="连线属性编辑" width="420px" @close="handleClose">
    <el-form label-width="80px">
      <el-form-item label="连线类型">
        <el-select v-model="formData.edge_type" style="width: 100%">
          <el-option label="正常流转" value="normal" />
          <el-option label="条件分支" value="branch" />
          <el-option label="异常跳转" value="exception" />
          <el-option label="旁路步骤" value="bypass" />
        </el-select>
      </el-form-item>

      <el-form-item label="触发条件">
        <el-input
          v-model="formData.condition"
          type="textarea"
          :rows="3"
          :placeholder="conditionPlaceholder"
        />
      </el-form-item>

      <el-form-item label="触发动作">
        <el-input v-model="formData.trigger_action" placeholder="例如：跳转到登录页、弹出确认框" />
      </el-form-item>

      <el-form-item label="前置操作">
        <el-input v-model="formData.pre_action" placeholder="例如：校验表单、保存草稿" />
      </el-form-item>

      <el-form-item label="备注">
        <el-input
          v-model="formData.note"
          type="textarea"
          :rows="2"
          placeholder="备注信息（可选）"
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
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'

interface EdgeConditionData {
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition: string | null
  trigger_action: string
  pre_action: string
  note: string
  label: string
}

interface EdgeFormData {
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition: string
  trigger_action: string
  pre_action: string
  note: string
}

const props = defineProps<{
  visible: boolean
  edgeData?: EdgeFormData | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [data: EdgeConditionData]
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const formData = ref<EdgeFormData>({
  edge_type: 'normal',
  condition: '',
  trigger_action: '',
  pre_action: '',
  note: '',
})

const conditionLabel = computed(() => {
  const labels: Record<string, string> = {
    branch: '触发条件',
    exception: '异常场景',
    bypass: '出现时机',
  }
  return labels[formData.value.edge_type] || '条件'
})

const conditionPlaceholder = computed(() => {
  const placeholders: Record<string, string> = {
    branch: '例如：用户点击高级筛选按钮',
    exception: '例如：输入非法字符或接口超时',
    bypass: '例如：进入页面自动弹出',
  }
  return placeholders[formData.value.edge_type] || ''
})

watch(
  () => props.visible,
  (val) => {
    if (val) {
      if (props.edgeData) {
        formData.value = { ...props.edgeData }
      } else {
        formData.value = {
          edge_type: 'normal',
          condition: '',
          trigger_action: '',
          pre_action: '',
          note: '',
        }
      }
    }
  },
  { immediate: true }
)

const handleClose = () => {
  formData.value = {
    edge_type: 'normal',
    condition: '',
    trigger_action: '',
    pre_action: '',
    note: '',
  }
}

const handleConfirm = () => {
  const normalizedCondition = formData.value.condition.trim()
  if (formData.value.edge_type !== 'normal' && !normalizedCondition) {
    ElMessage.warning(`请填写${conditionLabel.value}`)
    return
  }

  const labelMap: Record<string, string> = {
    normal: '正常流转',
    branch: '条件分支',
    exception: '异常跳转',
    bypass: '旁路步骤',
  }

  emit('confirm', {
    edge_type: formData.value.edge_type,
    condition: normalizedCondition || null,
    trigger_action: formData.value.trigger_action.trim(),
    pre_action: formData.value.pre_action.trim(),
    note: formData.value.note.trim(),
    label: labelMap[formData.value.edge_type],
  })
}
</script>
