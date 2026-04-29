<template>
  <el-dialog
    :model-value="modelValue"
    :title="dialogTitle"
    class="test-point-form-dialog"
    width="640px"
    @close="handleClose"
  >
    <div class="dialog-hero">
      <div class="hero-title">
        {{ props.editingPoint ? '更新测试点信息' : '创建新的测试点条目' }}
      </div>
      <div class="hero-subtitle">
        建议补齐模块、功能和 AI 提示词，后续生成用例时上下文会更完整。
      </div>
    </div>

    <div class="form-shell">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="模块" prop="module">
          <el-input
            v-model="formData.module"
            maxlength="100"
            show-word-limit
            placeholder="如：登录中心"
          />
        </el-form-item>
        <el-form-item label="测试点" prop="point">
          <el-input
            v-model="formData.point"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="描述本条测试点关注的行为、校验或边界情况"
          />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-select v-model="formData.priority" class="full-width">
            <el-option label="高" :value="1" />
            <el-option label="中" :value="2" />
            <el-option label="低" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="AI提示词" prop="ai_prompt">
          <el-input
            v-model="formData.ai_prompt"
            type="textarea"
            :rows="3"
            placeholder="可选，补充 AI 生成上下文"
          />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import { testPointApi } from '@/api/testPoint'
import type { TestPoint, TestPointFormData } from '@/types/testPoint'

const props = defineProps<{
  modelValue: boolean
  projectId: number
  editingPoint: TestPoint | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: []
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const dialogTitle = computed(() => (props.editingPoint ? '编辑测试点' : '新增测试点'))

const formData = reactive<TestPointFormData>({
  project_id: 0,
  module: '',
  point: '',
  priority: 2,
  ai_prompt: '',
})

const formRules: FormRules<TestPointFormData> = {
  module: [{ required: true, message: '请输入模块名称', trigger: 'blur' }],
  point: [{ required: true, message: '请输入测试点描述', trigger: 'blur' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
}

function resetFormData(): void {
  formData.project_id = props.projectId
  formData.module = props.editingPoint?.module ?? ''
  formData.point = props.editingPoint?.point ?? ''
  formData.priority = props.editingPoint?.priority ?? 2
  formData.ai_prompt = props.editingPoint?.ai_prompt ?? ''
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) {
    return
  }
  const isValid = await formRef.value.validate().catch(() => false)
  if (!isValid) {
    return
  }

  submitting.value = true
  try {
    if (props.editingPoint) {
      await testPointApi.update(props.editingPoint.id, formData)
      ElMessage.success('测试点更新成功')
    } else {
      await testPointApi.create(formData)
      ElMessage.success('测试点创建成功')
    }
    emit('success')
    emit('update:modelValue', false)
  } catch (error) {
    const message = error instanceof Error ? error.message : '保存失败'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}

function handleClose(): void {
  emit('update:modelValue', false)
}

watch(
  () => [props.modelValue, props.projectId, props.editingPoint] as const,
  ([visible]) => {
    if (visible) {
      resetFormData()
    } else {
      formRef.value?.resetFields()
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.full-width {
  width: 100%;
}

.dialog-hero {
  padding: 16px 18px;
  margin-bottom: 18px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.12), rgba(118, 75, 162, 0.08));
  border-radius: 18px;
}

.hero-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2d3d;
}

.hero-subtitle {
  margin-top: 6px;
  color: #6b7684;
  line-height: 1.6;
}

.form-shell {
  padding: 18px 18px 4px;
  border: 1px solid rgba(220, 230, 241, 0.9);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
}

.test-point-form-dialog :deep(.el-dialog) {
  border-radius: 24px;
  overflow: hidden;
}

.test-point-form-dialog :deep(.el-dialog__body) {
  padding-top: 8px;
}

.test-point-form-dialog :deep(.el-dialog__footer) {
  padding-top: 8px;
}
</style>
