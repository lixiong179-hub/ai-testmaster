<template>
  <div class="workbench">
    <el-row :gutter="16">
      <!-- 当前项目卡片 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="wb-card wb-project">
          <template #header>
            <div class="wb-card-header">
              <span class="wb-card-title">当前项目</span>
              <el-button link type="primary" @click="goToProjectList">项目中心</el-button>
            </div>
          </template>
          <!-- 无项目引导 -->
          <div v-if="!hasProject" class="wb-guide">
            <el-icon class="wb-guide-icon"><Plus /></el-icon>
            <p class="wb-guide-text">还没有项目，立即创建第一个项目开始测试</p>
            <el-button type="primary" :icon="Plus" @click="goToCreateProject">
              创建项目
            </el-button>
          </div>
          <!-- 骨架屏 -->
          <el-skeleton v-else-if="overviewLoading" :rows="4" animated />
          <!-- 概览内容 -->
          <div v-else-if="overview" class="wb-project-body">
            <div class="wb-project-name" :title="overview.name">{{ overview.name }}</div>
            <el-row :gutter="12" class="wb-project-stats">
              <el-col :span="6">
                <div class="wb-stat">
                  <div class="wb-stat-label">需求数</div>
                  <div class="wb-stat-value">{{ overview.requirementCount }}</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="wb-stat">
                  <div class="wb-stat-label">用例数</div>
                  <div class="wb-stat-value">{{ overview.caseCount }}</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="wb-stat">
                  <div class="wb-stat-label">质量分</div>
                  <div class="wb-stat-value">
                    {{ overview.qualityScore === null ? '—' : overview.qualityScore }}
                  </div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="wb-stat">
                  <div class="wb-stat-label">通过率</div>
                  <div class="wb-stat-value">{{ overview.passRate }}%</div>
                </div>
              </el-col>
            </el-row>
          </div>
          <el-empty v-else description="暂无项目数据" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 待我评审 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="wb-card wb-reviews">
          <template #header>
            <div class="wb-card-header">
              <span class="wb-card-title">待我评审</span>
              <el-button link type="primary" @click="goToReviewInbox(0)">查看全部</el-button>
            </div>
          </template>
          <el-skeleton v-if="reviewsLoading" :rows="4" animated />
          <div v-else-if="pendingReviews.length" class="wb-list">
            <div
              v-for="rv in pendingReviews"
              :key="rv.reviewId"
              class="wb-list-item"
              @click="goToReviewInbox(rv.reviewId)"
            >
              <div class="wb-list-main">
                <div class="wb-list-title">{{ reviewKindLabel(rv.kind) }} #{{ rv.reviewId }}</div>
                <div class="wb-list-sub">迭代 {{ rv.iterationId }}</div>
              </div>
              <el-tag size="small" type="warning">待评审</el-tag>
            </div>
          </div>
          <el-empty v-else-if="hasProject" description="暂无待评审项" :image-size="60" />
          <el-empty v-else description="请先选择项目" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="wb-row">
      <!-- 最近任务 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="wb-card wb-tasks">
          <template #header>
            <div class="wb-card-header">
              <span class="wb-card-title">最近任务</span>
              <el-button link type="primary" @click="goToTaskList">任务列表</el-button>
            </div>
          </template>
          <el-skeleton v-if="tasksLoading" :rows="4" animated />
          <div v-else-if="recentTasks.length" class="wb-list">
            <div
              v-for="task in recentTasks"
              :key="task.id"
              class="wb-list-item"
              @click="goToTaskDetail(task.id)"
            >
              <div class="wb-list-main">
                <div class="wb-list-title">{{ task.taskName }}</div>
                <div class="wb-list-sub">{{ formatTime(task.createTime) }}</div>
              </div>
              <el-tag size="small" :type="taskStatusTagType(task.status)">
                {{ taskStatusText(task.status) }}
              </el-tag>
            </div>
          </div>
          <el-empty v-else-if="hasProject" description="暂无任务" :image-size="60" />
          <el-empty v-else description="请先选择项目" :image-size="60" />
        </el-card>
      </el-col>

      <!-- AI 成本趋势 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="wb-card wb-cost">
          <template #header>
            <div class="wb-card-header">
              <span class="wb-card-title">AI 成本趋势（近7天）</span>
              <el-button link type="primary" @click="goToAICostDashboard">成本看板</el-button>
            </div>
          </template>
          <el-skeleton v-if="costLoading" :rows="5" animated />
          <div v-else-if="aiCostTrend.length">
            <div :ref="setCostChartRef" class="wb-chart" />
            <div class="wb-cost-summary">
              <span>7天合计：{{ totalCostCny }} 元</span>
              <span class="wb-cost-calls">调用 {{ totalCalls }} 次</span>
            </div>
          </div>
          <el-empty v-else-if="hasProject" description="暂无成本数据" :image-size="60" />
          <el-empty v-else description="请先选择项目" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { useWorkbench } from './useWorkbench'
import { TaskStatus } from '@/api/testTask'

const {
    hasProject,
    overview,
    overviewLoading,
    pendingReviews,
    reviewsLoading,
    recentTasks,
    tasksLoading,
    aiCostTrend,
    costLoading,
    totalCostCny,
    totalCalls,
    setCostChartRef,
    goToCreateProject,
    goToProjectList,
    goToTaskList,
    goToTaskDetail,
    goToReviewInbox,
    goToAICostDashboard,
} = useWorkbench()

type TagType = 'info' | 'primary' | 'success' | 'danger' | 'warning'

/** 评审类型文案映射 */
function reviewKindLabel(kind: string): string {
    const map: Record<string, string> = {
        case: '用例评审',
        point: '测试点评审',
        flow: '流程评审',
    }
    return map[kind] || '评审'
}

/** 任务状态文案 */
function taskStatusText(status: number): string {
    const map: Record<number, string> = {
        [TaskStatus.WAITING]: '等待执行',
        [TaskStatus.RUNNING]: '执行中',
        [TaskStatus.COMPLETED]: '执行完成',
        [TaskStatus.FAILED]: '执行失败',
        [TaskStatus.STOPPED]: '已停止',
    }
    return map[status] || '未知'
}

/** 任务状态标签颜色 */
function taskStatusTagType(status: number): TagType {
    const map: Record<number, TagType> = {
        [TaskStatus.WAITING]: 'info',
        [TaskStatus.RUNNING]: 'primary',
        [TaskStatus.COMPLETED]: 'success',
        [TaskStatus.FAILED]: 'danger',
        [TaskStatus.STOPPED]: 'warning',
    }
    return map[status] || 'info'
}

/** 格式化时间为 MM-DD HH:mm */
function formatTime(timeStr: string): string {
    if (!timeStr) return '-'
    const d = new Date(timeStr)
    if (isNaN(d.getTime())) return timeStr
    return d.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    })
}
</script>

<style scoped>
.workbench {
    padding: 16px;
}
.wb-row {
    margin-top: 16px;
}
.wb-card {
    height: 100%;
}
.wb-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.wb-card-title {
    font-weight: 600;
    color: var(--color-text-primary, #303133);
}
/* 无项目引导 */
.wb-guide {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 8px 8px;
    text-align: center;
}
.wb-guide-icon {
    font-size: 40px;
    color: var(--color-primary, #409eff);
    margin-bottom: 12px;
}
.wb-guide-text {
    margin: 0 0 16px;
    color: var(--color-text-secondary, #909399);
    font-size: 14px;
}
/* 项目概览 */
.wb-project-body {
    display: flex;
    flex-direction: column;
    gap: 16px;
}
.wb-project-name {
    font-size: 18px;
    font-weight: 600;
    color: var(--color-text-primary, #303133);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.wb-project-stats .wb-stat {
    text-align: center;
    padding: 8px 0;
    background: var(--color-fill-light, #f5f7fa);
    border-radius: 6px;
}
.wb-stat-label {
    font-size: 12px;
    color: var(--color-text-secondary, #909399);
    margin-bottom: 4px;
}
.wb-stat-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--color-primary, #409eff);
}
/* 列表区块 */
.wb-list {
    display: flex;
    flex-direction: column;
}
.wb-list-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 4px;
    border-bottom: 1px solid var(--color-border-light, #ebeef5);
    cursor: pointer;
    transition: background 0.2s;
}
.wb-list-item:last-child {
    border-bottom: none;
}
.wb-list-item:hover {
    background: var(--color-fill-light, #f5f7fa);
}
.wb-list-main {
    overflow: hidden;
}
.wb-list-title {
    font-size: 14px;
    color: var(--color-text-primary, #303133);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.wb-list-sub {
    font-size: 12px;
    color: var(--color-text-secondary, #909399);
    margin-top: 2px;
}
/* 成本图表 */
.wb-chart {
    width: 100%;
    height: 220px;
}
.wb-cost-summary {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
    font-size: 13px;
    color: var(--color-text-secondary, #909399);
}
.wb-cost-calls {
    color: var(--color-warning, #e6a23c);
}
</style>
