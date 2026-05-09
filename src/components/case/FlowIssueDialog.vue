<template>
  <el-dialog
    :model-value="visible"
    title="流程图完整性检查"
    width="580px"
    :close-on-click-modal="false"
    @close="$emit('cancel')"
  >
    <div class="issue-dialog-body">
      <el-alert
        v-if="validation.errors.length > 0"
        title="以下问题需要修复后才能继续生成"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-alert
        v-if="validation.errors.length === 0 && validation.warnings.length > 0"
        title="以下为流程提示，你可以选择继续生成或返回调整"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <div class="issue-list">
        <div
          v-for="(issue, index) in validation.errors"
          :key="'err-' + index"
          class="issue-item issue-error"
        >
          <el-icon><CircleClose /></el-icon>
          <span>{{ issue }}</span>
        </div>
        <div
          v-for="(issue, index) in validation.warnings"
          :key="'warn-' + index"
          class="issue-item issue-warning"
        >
          <el-icon><WarningFilled /></el-icon>
          <span>{{ issue }}</span>
        </div>
      </div>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="$emit('cancel')">返回调整</el-button>
        <el-button v-if="validation.errors.length === 0" type="primary" @click="$emit('confirm')">
          继续生成
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { CircleClose, WarningFilled } from '@element-plus/icons-vue'

defineProps<{
  visible: boolean
  validation: {
    errors: string[]
    warnings: string[]
  }
}>()

defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<style scoped>
.issue-dialog-body {
  padding: 4px 0;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.issue-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
}

.issue-item .el-icon {
  flex-shrink: 0;
  margin-top: 1px;
}

.issue-error {
  background: #fef0f0;
  color: #c45656;
  border: 1px solid #fbc4c4;
}

.issue-warning {
  background: #fdf6ec;
  color: #b88230;
  border: 1px solid #f5dab1;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
