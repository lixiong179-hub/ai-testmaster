<template>
  <el-dialog
    :model-value="visible"
    :title="title || '确认操作'"
    :close-on-click-modal="false"
    width="560px"
    @close="$emit('cancel')"
  >
    <div v-if="reason" class="pause-reason">
      <el-alert :title="reason" type="warning" :closable="false" show-icon />
    </div>

    <el-form
      v-if="fields.length > 0"
      ref="formRef"
      :model="formData"
      label-width="100px"
      class="confirmation-form"
    >
      <el-form-item
        v-for="field in fields"
        :key="field.key"
        :label="field.label"
        :required="field.required"
      >
        <el-select
          v-if="field.type === 'select'"
          v-model="formData[field.key] as any"
          :placeholder="field.placeholder || '请选择'"
        >
          <el-option
            v-for="opt in field.options || []"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>

        <el-input
          v-else-if="field.type === 'textarea'"
          v-model="formData[field.key] as any"
          type="textarea"
          :rows="3"
          :placeholder="field.placeholder || '请输入'"
        />

        <el-input
          v-else-if="field.type === 'number'"
          v-model.number="formData[field.key] as any"
          type="number"
          :placeholder="field.placeholder || '请输入'"
        />

        <el-input
          v-else
          v-model="formData[field.key] as any"
          :placeholder="field.placeholder || '请输入'"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('cancel')">取消</el-button>
      <el-button type="primary" @click="handleConfirm">确认并继续</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'

interface SchemaField {
  key: string
  label: string
  type: 'select' | 'textarea' | 'number' | 'text'
  options?: { label: string; value: string }[]
  placeholder?: string
  required?: boolean
}

const props = defineProps<{
  visible: boolean
  title?: string
  reason?: string
  schema?: { fields: SchemaField[] } | null
}>()

const emit = defineEmits<{
  confirm: [payload: Record<string, unknown>]
  cancel: []
}>()

const fields = ref<SchemaField[]>([])
const formData = reactive<Record<string, unknown>>({})

watch(
  () => props.schema,
  (s) => {
    if (s && Array.isArray(s.fields)) {
      fields.value = s.fields
      const initial: Record<string, unknown> = {}
      for (const field of s.fields) {
        initial[field.key] = field.type === 'number' ? 0 : ''
      }
      Object.assign(formData, initial)
    } else {
      fields.value = []
    }
  },
  { immediate: true }
)

function handleConfirm() {
  emit('confirm', { ...formData })
}
</script>

<style scoped>
.pause-reason {
  margin-bottom: 16px;
}

.confirmation-form {
  margin-top: 8px;
}
</style>
