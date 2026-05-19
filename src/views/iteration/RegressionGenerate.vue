<template>
  <div class="regression-generate-container">
    <div class="page-header">
      <el-button @click="goBack" :icon="ArrowLeft" circle size="small" />
      <h2>旧项目变更分析</h2>
      <el-tag v-if="precheckData" :type="precheckData.can_run ? 'success' : 'danger'" size="large">
        {{ precheckData.can_run ? '满足运行条件' : '暂不满足条件' }}
      </el-tag>
    </div>

    <el-row :gutter="20" v-loading="precheckLoading">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>项目信息</span>
              <el-tag size="small" type="primary">项目 #{{ projectId }}</el-tag>
            </div>
          </template>
          <div class="info-row">
            <span class="info-label">UI 原型名称</span>
            <span class="info-value">{{ prototypeName }}</span>
          </div>
          <div class="info-row" v-if="precheckData">
            <span class="info-label">可用 UI 页面</span>
            <span class="info-value">{{ precheckData.ui.parsed_screen_count }} 个已解析</span>
            <el-tag v-if="precheckData.ui.unparsed_screen_count > 0" type="warning" size="small">
              另有 {{ precheckData.ui.unparsed_screen_count }} 个未解析
            </el-tag>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>历史用例扫描范围</span>
            </div>
          </template>
          <div v-if="precheckData" class="scan-stats">
            <div class="scan-stat-row">
              <span class="stat-label">总历史用例</span>
              <span class="stat-value">{{ precheckData.history_cases.total }}</span>
            </div>
            <div class="scan-stat-row highlight">
              <span class="stat-label">参与扫描</span>
              <span class="stat-value">{{ precheckData.history_cases.included }}</span>
            </div>
            <div class="scan-stat-row">
              <span class="stat-label">active</span>
              <span class="stat-value">{{ precheckData.history_cases.active }}</span>
            </div>
            <div class="scan-stat-row">
              <span class="stat-label">draft</span>
              <span class="stat-value">{{ precheckData.history_cases.draft }}</span>
            </div>
            <div class="scan-stat-row">
              <span class="stat-label">待评审</span>
              <span class="stat-value">{{ precheckData.history_cases.pending_review }}</span>
            </div>
            <div class="scan-stat-row excluded">
              <span class="stat-label">已排除(archived)</span>
              <span class="stat-value">{{ precheckData.history_cases.archived }}</span>
            </div>
            <div class="scan-stat-row excluded">
              <span class="stat-label">已排除(已删除)</span>
              <span class="stat-value">{{ precheckData.history_cases.deleted }}</span>
            </div>
          </div>
          <div v-else class="empty-hint">
            <el-empty description="暂无数据" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="config-card" v-if="precheckData">
      <template #header>
        <div class="card-header">
          <span>配置与启动</span>
        </div>
      </template>

      <el-form label-width="120px">
        <el-form-item label="迭代">
          <div class="iteration-select-row">
            <el-select
              v-model="selectedIterationId"
              placeholder="选择已有迭代（或创建新迭代）"
              style="width: 320px"
              filterable
              clearable
            >
              <el-option
                v-for="it in iterations"
                :key="it.id"
                :label="`${it.name}${it.version ? ' (' + it.version + ')' : ''}`"
                :value="it.id"
              />
            </el-select>
            <el-button type="primary" plain @click="showCreateIteration = true">
              创建新迭代
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="测试点" v-if="precheckData.test_points.total > 0">
          <el-select
            v-model="selectedTestPointIds"
            multiple
            filterable
            placeholder="选择测试点（可选，建议选择以获得更精确的对齐结果）"
            style="width: 100%"
            collapse-tags
            collapse-tags-tooltip
          >
            <el-option
              v-for="tp in testPoints"
              :key="tp.id"
              :label="`${tp.module} - ${tp.point}`"
              :value="tp.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="变更说明">
          <el-input
            v-model="changeNotes"
            type="textarea"
            :rows="2"
            placeholder="可选：输入本次变更的简要说明（如新增了哪些功能、修改了哪些页面）"
          />
        </el-form-item>
      </el-form>

      <el-alert
        v-if="precheckData.blocking_reasons.length > 0"
        :title="precheckData.blocking_reasons.join('；')"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <el-alert
        v-for="(w, idx) in precheckData.warnings"
        :key="idx"
        :title="w"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 8px"
      />

      <el-alert
        title="历史用例会自动扫描，不需要手动逐条选择旧用例。场景 4 会自动扫描当前项目下非 archived、未删除的历史用例。"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <div class="start-section">
        <el-button
          type="danger"
          size="large"
          :disabled="!canStart"
          :loading="starting"
          @click="handleStart"
        >
          开始旧项目变更分析
        </el-button>
        <span v-if="!selectedIterationId" class="start-hint">请先选择或创建一个迭代</span>
        <span v-else-if="!precheckData.can_run" class="start-hint">不满足运行条件</span>
        <span v-else class="start-hint">
          将调用场景 4 Pipeline，分析 {{ precheckData.history_cases.included }} 个历史用例
        </span>
      </div>
    </el-card>

    <el-dialog
      v-model="showCreateIteration"
      title="创建新迭代"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="newIterationForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="newIterationForm.name" placeholder="如：v2.0 首页重构" />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="newIterationForm.version" placeholder="如：2.0.0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="newIterationForm.description"
            type="textarea"
            :rows="2"
            placeholder="迭代描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateIteration = false">取消</el-button>
        <el-button type="primary" :loading="creatingIteration" @click="handleCreateIteration">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft } from '@element-plus/icons-vue'
import { useRegressionGenerate } from './useRegressionGenerate'

const {
  projectId, prototypeName, precheckLoading, precheckData,
  iterations, selectedIterationId, showCreateIteration, creatingIteration, newIterationForm,
  testPoints, selectedTestPointIds, changeNotes, starting, canStart,
  goBack, handleCreateIteration, handleStart,
} = useRegressionGenerate()
</script>

<style scoped lang="scss">
@import './RegressionGenerate.scss';
</style>
