<template>
  <div class="self-healing-config-tab" v-loading="loading">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="config-tip"
    >
      项目级自愈配置，启用后将在用例执行时自动修复失效元素定位器。
      项目开关受全局开关约束：全局关闭时项目级启用亦不生效。
    </el-alert>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="120px"
      class="config-form"
    >
      <el-form-item label="启用自愈" prop="enabled">
        <el-switch v-model="form.enabled" />
        <span class="form-hint">关闭后该项目不触发自动修复</span>
      </el-form-item>

      <el-form-item label="修复策略" prop="strategies">
        <el-select
          v-model="form.strategies"
          multiple
          placeholder="选择修复策略"
          style="width: 360px"
        >
          <el-option
            v-for="opt in strategyOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <span class="form-hint">多选，按顺序尝试</span>
      </el-form-item>

      <el-form-item label="Token 限额" prop="token_limit">
        <el-input-number v-model="form.token_limit" :min="1" :max="10000" />
        <span class="form-hint">单次自愈消耗 Token 上限（1-10000）</span>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="saving" @click="handleSave">
          保存配置
        </el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import selfHealingApi from '@/api/selfHealing'
import { strategyOptions } from '@/api/selfHealing'

const props = defineProps<{
  projectId: number
}>()

const formRef = ref<FormInstance>()
const loading = ref(false)
const saving = ref(false)

const form = reactive({
  enabled: false,
  strategies: [] as string[],
  token_limit: 1000,
})

const rules: FormRules = {
  strategies: [
    {
      required: true,
      message: '请至少选择一个修复策略',
      trigger: 'change',
    },
  ],
  token_limit: [
    {
      required: true,
      message: '请输入 Token 限额',
      trigger: 'blur',
    },
  ],
}

/** 加载项目自愈配置 */
const loadConfig = async (): Promise<void> => {
  if (!props.projectId) return
  loading.value = true
  try {
    const res = await selfHealingApi.getConfig(props.projectId)
    const data = res?.data
    if (data) {
      form.enabled = data.enabled
      form.strategies = [...(data.strategies ?? [])]
      form.token_limit = data.token_limit
    }
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : '获取自愈配置失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

/** 保存项目自愈配置 */
const handleSave = async (): Promise<void> => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    // 校验未通过，保持当前状态等待用户修正
    return
  }
  saving.value = true
  try {
    const res = await selfHealingApi.updateConfig(props.projectId, {
      enabled: form.enabled,
      strategies: form.strategies,
      token_limit: form.token_limit,
    })
    if (res.code === 200) {
      ElMessage.success('自愈配置保存成功')
      // 回填后端合并后的配置（enabled 可能被全局开关收敛为 false）
      const data = res.data
      if (data) {
        form.enabled = data.enabled
        form.strategies = [...(data.strategies ?? [])]
        form.token_limit = data.token_limit
      }
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : '保存失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped lang="scss">
.self-healing-config-tab {
  max-width: 720px;
}
.config-tip {
  margin-bottom: 20px;
}
.config-form {
  margin-top: 10px;
}
.form-hint {
  margin-left: 12px;
  font-size: 12px;
  color: #909399;
}
</style>
