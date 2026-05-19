<template>
  <div class="page-header">
    <div class="header-left">
      <el-button type="info" @click="ctx.goBack" :icon="ArrowLeft"> 返回 </el-button>
      <h2>测试用例详情</h2>
      <el-tag v-if="ctx.caseItem.value" type="info">
        {{ ctx.caseItem.value.case_no }}
      </el-tag>
      <el-tag v-if="ctx.isCorrectionMode.value" type="warning" effect="dark"> 纠正模式 </el-tag>
    </div>
    <div class="header-right">
      <el-radio-group
        v-if="!ctx.isEditing.value"
        v-model="ctx.currentView.value"
        size="small"
        @change="ctx.handleViewChange"
      >
        <el-radio-button :value="VIEW_TYPES.BUSINESS">业务视图</el-radio-button>
        <el-radio-button :value="VIEW_TYPES.TECHNICAL">技术视图</el-radio-button>
      </el-radio-group>
      <el-button
        type="success"
        @click="ctx.copyCase"
        :icon="DocumentCopy"
        :disabled="ctx.issueType.value === 'product_bug'"
      >
        复制用例
      </el-button>
      <el-button @click="ctx.openVersionHistory" :disabled="!ctx.caseId.value"> 版本历史 </el-button>
      <el-button :loading="ctx.exportingExcel.value" :disabled="!ctx.caseId.value" @click="ctx.handleExportExcel">
        导出Excel
      </el-button>
      <el-button
        v-if="ctx.issueType.value !== 'product_bug'"
        type="primary"
        @click="ctx.toggleEdit"
        :icon="ctx.isEditing.value ? Close : Edit"
      >
        {{ ctx.isEditing.value ? '取消' : '编辑' }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, Edit, Close, DocumentCopy } from '@element-plus/icons-vue'
import { useCaseDetail, VIEW_TYPES } from '@/composables/case/useCaseDetail'

const ctx = useCaseDetail()
</script>
