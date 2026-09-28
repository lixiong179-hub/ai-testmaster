<template>
  <div class="quality-rule-tab" v-loading="loading">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="config-tip"
    >
      项目级质量规则配置，影响该项目用例的质量评分、覆盖率统计与质量门禁判定。修改后立即生效。
    </el-alert>

    <el-table :data="rules" style="width: 100%" border stripe size="small">
      <el-table-column prop="rule_key" label="规则Key" width="240" show-overflow-tooltip />
      <el-table-column label="默认值" width="140">
        <template #default="scope">
          {{ formatRuleValue(scope.row.default_value) }}
        </template>
      </el-table-column>
      <el-table-column label="当前值" min-width="180">
        <template #default="scope">
          <span :class="{ 'value-modified': !isDefaultValue(scope.row) }">
            {{ formatRuleValue(scope.row.rule_value) }}
          </span>
          <el-tag
            v-if="!isDefaultValue(scope.row)"
            type="warning"
            size="small"
            style="margin-left: 8px"
          >
            已修改
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
        <template #default="scope">
          {{ scope.row.description || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="openEditDialog(scope.row)">编辑</el-button>
          <el-button
            size="small"
            type="warning"
            :disabled="isDefaultValue(scope.row)"
            @click="resetToDefault(scope.row)"
          >恢复默认</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-if="!loading && rules.length === 0"
      description="暂无质量规则数据"
    />

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" title="编辑规则" width="520px" destroy-on-close>
      <el-form :ref="setFormRef" :model="formData" label-width="100px">
        <el-form-item label="规则Key">
          <el-input :model-value="formData.rule_key" disabled />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            :model-value="currentRule?.description ?? ''"
            disabled
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <el-form-item v-if="currentRule?.value_type === 'boolean'" label="规则值">
          <el-switch
            v-model="formData.rule_value_bool"
            active-text="是"
            inactive-text="否"
          />
        </el-form-item>
        <el-form-item v-else-if="currentRule?.value_type === 'number'" label="规则值">
          <el-input-number
            v-model="formData.rule_value_num"
            :min="0"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-else-if="currentRule?.value_type === 'enum'" label="规则值">
          <el-select v-model="formData.rule_value_str" placeholder="请选择" style="width: 100%">
            <el-option
              v-for="opt in (currentRule?.enum_options ?? [])"
              :key="opt"
              :label="opt"
              :value="opt"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="规则值">
          <el-input v-model="formData.rule_value_str" placeholder="请输入规则值" />
        </el-form-item>
        <el-form-item label="默认值">
          <el-tag type="info">{{ formatRuleValue(currentRule?.default_value ?? '') }}</el-tag>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveRule">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { qualityRuleApi } from '@/api/qualityRule'
import type { QualityRuleItem } from '@/api/qualityRule'

const props = defineProps<{
  projectId: number
}>()

const loading = ref(false)
const saving = ref(false)
const rules = ref<QualityRuleItem[]>([])

const dialogVisible = ref(false)
const currentRule = ref<QualityRuleItem | null>(null)
const formRef = ref<FormInstance>()

interface RuleFormData {
  rule_key: string
  rule_value_str: string
  rule_value_num: number
  rule_value_bool: boolean
}

const formData = reactive<RuleFormData>({
  rule_key: '',
  rule_value_str: '',
  rule_value_num: 0,
  rule_value_bool: false,
})

const currentRuleValue = computed<string | number | boolean>(() => {
  const rule = currentRule.value
  if (!rule) return ''
  switch (rule.value_type) {
    case 'boolean':
      return formData.rule_value_bool
    case 'number':
      return formData.rule_value_num
    case 'enum':
      return formData.rule_value_str
    default:
      return formData.rule_value_str
  }
})

const setFormRef = (el: unknown) => {
  formRef.value = el as FormInstance | undefined
}

const loadRules = async (): Promise<void> => {
  if (!props.projectId) {
    rules.value = []
    return
  }
  loading.value = true
  try {
    const response = await qualityRuleApi.getQualityRules(props.projectId)
    rules.value = Array.isArray(response.data) ? response.data : []
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : '获取质量规则失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const formatRuleValue = (value: string | number | boolean): string => {
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

const isDefaultValue = (row: QualityRuleItem): boolean => {
  return row.rule_value === row.default_value
}

const openEditDialog = (row: QualityRuleItem): void => {
  currentRule.value = row
  formData.rule_key = row.rule_key
  switch (row.value_type) {
    case 'boolean':
      formData.rule_value_bool = Boolean(row.rule_value)
      break
    case 'number':
      formData.rule_value_num = Number(row.rule_value)
      break
    default:
      formData.rule_value_str = String(row.rule_value)
      break
  }
  dialogVisible.value = true
}

const saveRule = async (): Promise<void> => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    await qualityRuleApi.updateQualityRule(props.projectId, {
      rule_key: formData.rule_key,
      rule_value: currentRuleValue.value,
    })
    ElMessage.success('规则更新成功')
    dialogVisible.value = false
    await loadRules()
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : '更新规则失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

const resetToDefault = (row: QualityRuleItem): void => {
  ElMessageBox.confirm(
    `确定要将规则「${row.rule_key}」恢复为默认值「${formatRuleValue(row.default_value)}」吗？`,
    '恢复默认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
    .then(async () => {
      try {
        await qualityRuleApi.updateQualityRule(props.projectId, {
          rule_key: row.rule_key,
          rule_value: row.default_value,
        })
        ElMessage.success('已恢复默认值')
        await loadRules()
      } catch (error: unknown) {
        const msg = error instanceof Error ? error.message : '恢复默认值失败'
        ElMessage.error(msg)
      }
    })
    .catch(() => {
      /* 用户取消 */
    })
}

watch(
  () => props.projectId,
  (newVal) => {
    if (newVal) loadRules()
    else rules.value = []
  }
)

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.quality-rule-tab {
  padding: 4px 0;
}
.config-tip {
  margin-bottom: 16px;
}
.value-modified {
  color: var(--color-warning, #e6a23c);
  font-weight: 500;
}
.dialog-footer {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
