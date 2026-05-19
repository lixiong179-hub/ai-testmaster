<template>
  <div class="quality-page">
    <div class="page-hero">
      <h2 class="page-title">用例质量分析</h2>
      <el-select v-model="selectedProjectId" placeholder="请选择项目" filterable @change="handleProjectChange">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
    </div>
    <div v-if="analysisResult" class="analysis-content" v-loading="loading">
      <div class="score-card">
        <div class="score-ring" :class="scoreLevel">
          <svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="50" fill="none" stroke="#e4e7ed" stroke-width="10" /><circle cx="60" cy="60" r="50" fill="none" :stroke="scoreLevel === 'success' ? '#67c23a' : scoreLevel === 'warning' ? '#e6a23c' : '#f56c6c'" stroke-width="10" :stroke-dasharray="`${overallScore * 3.14} 314`" stroke-linecap="round" transform="rotate(-90 60 60)" /></svg>
          <div class="score-text"><span class="score-num">{{ overallScore }}</span><span class="score-label">{{ scoreLabel }}</span></div>
        </div>
        <div class="score-desc">综合评分基于覆盖率、复杂度、冗余度和成本四个维度加权计算</div>
      </div>
      <div class="analysis-cards">
        <el-card v-for="dim in analysisResult.dimensions" :key="dim.name" class="dim-card" shadow="hover" @click="showDetail(dim.detail || dim.name)">
          <div class="dim-header"><span class="dim-name">{{ dim.label || dim.name }}</span><el-tag :type="dim.score >= 80 ? 'success' : dim.score >= 60 ? 'warning' : 'danger'" size="small">{{ dim.score }}分</el-tag></div>
          <el-progress :percentage="dim.score" :stroke-width="8" :color="dim.score >= 80 ? '#67c23a' : dim.score >= 60 ? '#e6a23c' : '#f56c6c'" />
          <p class="dim-summary">{{ dim.summary }}</p>
          <div v-if="dim.suggestions && dim.suggestions.length" class="dim-suggestions">
            <div v-for="(s, i) in dim.suggestions.slice(0, 3)" :key="i" class="suggestion-item"><el-icon color="#e6a23c"><Warning /></el-icon><span>{{ s }}</span></div>
          </div>
        </el-card>
      </div>
      <div v-if="analysisResult.optimization" class="optimization-section">
        <h3>优化建议</h3>
        <el-table :data="analysisResult.optimization.items" border stripe size="small">
          <el-table-column prop="type" label="类型" width="100" />
          <el-table-column prop="target" label="目标" min-width="200" show-overflow-tooltip />
          <el-table-column prop="action" label="建议操作" min-width="200" show-overflow-tooltip />
          <el-table-column prop="impact" label="预期影响" width="120" />
        </el-table>
      </div>
    </div>
    <el-empty v-else-if="!loading" description="请选择项目后查看质量分析" />
    <el-dialog v-model="dialogVisible" title="详细分析" width="600px"><div v-html="dialogContent" /></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Warning } from '@element-plus/icons-vue'
import { useCaseQualityAnalysis } from './useCaseQualityAnalysis'

const {
  loading, projects, selectedProjectId, analysisResult, dialogVisible,
  dialogContent, overallScore, scoreLevel, scoreLabel, handleProjectChange, showDetail,
} = useCaseQualityAnalysis()
</script>

<style scoped>
.quality-page { padding: 20px; background: #f7faff; min-height: 100vh; }
.page-hero { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 24px; background: #fff; border-radius: 20px; box-shadow: 0 10px 28px rgba(31, 45, 61, 0.05); }
.page-title { margin: 0; font-size: 24px; color: #1f2d3d; }
.analysis-content { display: flex; flex-direction: column; gap: 20px; }
.score-card { display: flex; align-items: center; gap: 32px; padding: 28px; background: #fff; border-radius: 20px; box-shadow: 0 10px 28px rgba(31, 45, 61, 0.05); }
.score-ring { position: relative; width: 120px; height: 120px; flex-shrink: 0; }
.score-ring svg { width: 100%; height: 100%; }
.score-text { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.score-num { font-size: 32px; font-weight: 700; color: #1f2d3d; }
.score-label { font-size: 12px; color: #909399; }
.score-desc { font-size: 14px; color: #606266; line-height: 1.6; max-width: 400px; }
.analysis-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.dim-card { cursor: pointer; transition: transform 0.2s; }
.dim-card:hover { transform: translateY(-2px); }
.dim-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.dim-name { font-weight: 600; color: #303133; }
.dim-summary { font-size: 13px; color: #606266; margin: 12px 0 8px; line-height: 1.5; }
.dim-suggestions { display: flex; flex-direction: column; gap: 6px; }
.suggestion-item { display: flex; align-items: flex-start; gap: 6px; font-size: 12px; color: #e6a23c; }
.optimization-section { padding: 24px; background: #fff; border-radius: 20px; box-shadow: 0 10px 28px rgba(31, 45, 61, 0.05); }
.optimization-section h3 { margin: 0 0 16px; color: #1f2d3d; }
</style>
