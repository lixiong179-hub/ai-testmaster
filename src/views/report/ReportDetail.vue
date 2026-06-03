<template>
  <div class="report-detail">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>缺陷报告详情</span>
          <div>
            <el-dropdown trigger="click" :disabled="exportLoading">
              <el-button type="primary" size="small" :loading="exportLoading">
                导出 <el-icon class="el-icon--right"><arrow-down /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleExportPDF">导出PDF</el-dropdown-item>
                  <el-dropdown-item @click="handleExportHTML">导出HTML</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button type="primary" size="small" @click="goBack" style="margin-left: 10px">
              返回列表
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="report" class="report-content">
        <!-- 报告基本信息 -->
        <el-card shadow="hover" class="mb-4">
          <el-form :model="report" label-width="120px">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="报告名称">
                  <el-input v-model="report.name" disabled />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="项目">
                  <el-input v-model="report.project_name" disabled />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="创建时间">
                  <el-input v-model="report.create_time" disabled />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-card>

        <!-- ==================== 1. 缺陷概览卡片（首屏核心） ==================== -->
        <el-card shadow="hover" class="mb-4">
          <template #header>
            <div class="section-header">
              <span class="section-title">缺陷概览</span>
              <el-tag v-if="defectOverview" :type="defectOverview.total_count > 0 ? 'danger' : 'success'" size="large">
                共 {{ defectOverview.total_count }} 个缺陷
              </el-tag>
            </div>
          </template>

          <template v-if="defectOverview">
            <!-- 覆盖不足警告 -->
            <el-alert
              v-if="defectOverview.coverage_insufficient_warning"
              title="所有用例通过但未发现缺陷，可能覆盖不足"
              type="warning"
              show-icon
              :closable="false"
              class="mb-4"
            />

            <!-- 4 个严重度统计卡片 -->
            <el-row :gutter="16" class="mb-4">
              <el-col :span="6">
                <el-card shadow="hover" class="stat-card stat-card--danger">
                  <div class="stat-item">
                    <div class="stat-label">P0 致命</div>
                    <div class="stat-value">{{ defectOverview.p0_count }}</div>
                  </div>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover" class="stat-card stat-card--danger">
                  <div class="stat-item">
                    <div class="stat-label">P1 严重</div>
                    <div class="stat-value">{{ defectOverview.p1_count }}</div>
                  </div>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover" class="stat-card stat-card--warning">
                  <div class="stat-item">
                    <div class="stat-label">P2 一般</div>
                    <div class="stat-value">{{ defectOverview.p2_count }}</div>
                  </div>
                </el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover" class="stat-card stat-card--info">
                  <div class="stat-item">
                    <div class="stat-label">P3 轻微</div>
                    <div class="stat-value">{{ defectOverview.p3_count }}</div>
                  </div>
                </el-card>
              </el-col>
            </el-row>

            <!-- 关键指标行 -->
            <el-row :gutter="16">
              <el-col :span="8">
                <div class="metric-item">
                  <span class="metric-label">缺陷密度</span>
                  <span class="metric-value">{{ defectOverview.defect_density.toFixed(2) }}</span>
                  <span class="metric-unit">缺陷/用例</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="metric-item">
                  <span class="metric-label">高严重度占比</span>
                  <span class="metric-value">{{ (defectOverview.high_severity_ratio * 100).toFixed(1) }}%</span>
                  <span class="metric-unit">P0+P1</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="metric-item">
                  <span class="metric-label">缺陷发现覆盖率</span>
                  <span class="metric-value">{{ (defectOverview.defect_coverage_rate * 100).toFixed(1) }}%</span>
                </div>
              </el-col>
            </el-row>
          </template>

          <!-- 无缺陷数据时的占位 -->
          <el-empty v-else description="暂无缺陷概览数据" :image-size="80" />
        </el-card>

        <!-- ==================== 2. 缺陷清单（按严重度排序） ==================== -->
        <el-card shadow="hover" class="mb-4">
          <template #header>
            <div class="section-header">
              <span class="section-title">缺陷清单</span>
              <el-tag v-if="sortedDefectList.length > 0" type="info" size="small">
                共 {{ sortedDefectList.length }} 条
              </el-tag>
            </div>
          </template>

          <el-table
            v-if="sortedDefectList.length > 0"
            :data="sortedDefectList"
            style="width: 100%"
            border
            stripe
            row-key="bug_no"
            :default-sort="{ prop: 'severity', order: 'ascending' }"
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="expand-content">
                  <div v-if="row.reproduction_steps" class="expand-section">
                    <h4>复现步骤</h4>
                    <pre class="expand-pre">{{ row.reproduction_steps }}</pre>
                  </div>
                  <div v-if="row.evidence && Object.keys(row.evidence).length > 0" class="expand-section">
                    <h4>缺陷证据</h4>
                    <pre class="expand-pre">{{ formatJson(row.evidence) }}</pre>
                  </div>
                  <div v-if="row.ai_analysis" class="expand-section">
                    <h4>AI 分析</h4>
                    <p>{{ row.ai_analysis }}</p>
                  </div>
                  <div v-if="row.fix_suggestion" class="expand-section">
                    <h4>修复建议</h4>
                    <p>{{ row.fix_suggestion }}</p>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="bug_no" label="Bug编号" width="150" />
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="severity" label="严重度" width="100" sortable>
              <template #default="{ row }">
                <el-tag :type="severityTagType(row.severity)" size="small">
                  {{ severityLabel(row.severity) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="ux_category" label="分类" width="160">
              <template #default="{ row }">
                <span>{{ row.ux_category || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="module" label="功能模块" width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <span>{{ row.module || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="bugStatusType(row.status)" size="small" effect="plain">
                  {{ bugStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-else description="暂无缺陷记录" :image-size="80" />
        </el-card>

        <!-- ==================== 3. 缺陷分布图表 ==================== -->
        <el-card v-if="defectDistribution" shadow="hover" class="mb-4">
          <template #header>
            <div class="section-header">
              <span class="section-title">缺陷分布</span>
            </div>
          </template>

          <el-row :gutter="20">
            <el-col :span="12">
              <div class="chart-container">
                <h4 class="chart-title">按功能模块分布</h4>
                <div ref="moduleChartRef" class="chart"></div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="chart-container">
                <h4 class="chart-title">按缺陷类型分布</h4>
                <div ref="categoryChartRef" class="chart"></div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- ==================== 4. 隐性缺陷 ==================== -->
        <el-card v-if="hasImplicitDefects" shadow="hover" class="mb-4">
          <template #header>
            <div class="section-header">
              <span class="section-title">隐性缺陷</span>
              <el-tag type="warning" size="small">即使所有用例通过仍展示</el-tag>
            </div>
          </template>

          <el-collapse v-model="implicitActiveNames">
            <!-- 控制台错误 -->
            <el-collapse-item
              v-if="implicitDefects!.console_errors.length > 0"
              :name="'console'"
            >
              <template #title>
                <span class="collapse-title">
                  控制台错误
                  <el-badge :value="implicitDefects!.console_errors.length" type="danger" />
                </span>
              </template>
              <el-table :data="implicitDefects!.console_errors" border stripe size="small">
                <el-table-column prop="error_type" label="错误类型" width="180" />
                <el-table-column prop="message" label="消息" min-width="250" show-overflow-tooltip />
                <el-table-column prop="source" label="来源" width="200" show-overflow-tooltip />
                <el-table-column prop="timestamp" label="时间" width="180" />
              </el-table>
            </el-collapse-item>

            <!-- 网络失败 -->
            <el-collapse-item
              v-if="implicitDefects!.network_failures.length > 0"
              :name="'network'"
            >
              <template #title>
                <span class="collapse-title">
                  网络失败
                  <el-badge :value="implicitDefects!.network_failures.length" type="danger" />
                </span>
              </template>
              <el-table :data="implicitDefects!.network_failures" border stripe size="small">
                <el-table-column prop="method" label="方法" width="80" />
                <el-table-column prop="url" label="URL" min-width="250" show-overflow-tooltip />
                <el-table-column prop="status_code" label="状态码" width="90" />
                <el-table-column prop="duration" label="耗时(ms)" width="100" />
                <el-table-column prop="timestamp" label="时间" width="180" />
              </el-table>
            </el-collapse-item>

            <!-- 内存泄漏嫌疑 -->
            <el-collapse-item
              v-if="implicitDefects!.memory_leaks.length > 0"
              :name="'memory'"
            >
              <template #title>
                <span class="collapse-title">
                  内存泄漏嫌疑
                  <el-badge :value="implicitDefects!.memory_leaks.length" type="warning" />
                </span>
              </template>
              <el-table :data="implicitDefects!.memory_leaks" border stripe size="small">
                <el-table-column prop="description" label="描述" min-width="250" />
                <el-table-column prop="evidence" label="证据" min-width="200" show-overflow-tooltip />
                <el-table-column prop="severity" label="严重程度" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.severity === 'high' ? 'danger' : 'warning'" size="small">
                      {{ row.severity }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </el-collapse-item>
          </el-collapse>
        </el-card>

        <!-- ==================== 5. 安全发现 ==================== -->
        <el-card v-if="securityFindings.length > 0" shadow="hover" class="mb-4">
          <template #header>
            <div class="section-header">
              <span class="section-title" style="color: #f56c6c;">安全发现</span>
              <el-badge :value="securityFindings.length" type="danger" />
            </div>
          </template>

          <el-alert
            v-for="(finding, idx) in securityFindings"
            :key="idx"
            :title="`[${finding.type}] ${finding.description}`"
            type="error"
            show-icon
            :closable="false"
            class="mb-3"
          >
            <template #default>
              <div class="security-detail">
                <p v-if="finding.evidence"><strong>证据：</strong>{{ finding.evidence }}</p>
                <p><strong>严重程度：</strong>
                  <el-tag :type="finding.severity === 'critical' ? 'danger' : 'warning'" size="small">
                    {{ finding.severity }}
                  </el-tag>
                </p>
              </div>
            </template>
          </el-alert>
        </el-card>

        <!-- ==================== 6. 覆盖评估 ==================== -->
        <el-card v-if="coverageAssessment" shadow="hover" class="mb-4">
          <template #header>
            <div class="section-header">
              <span class="section-title">覆盖评估</span>
              <el-progress
                :percentage="Number((coverageAssessment.coverage_rate * 100).toFixed(1))"
                :color="coverageColor"
                :stroke-width="18"
                :text-inside="true"
                style="width: 200px;"
              />
            </div>
          </template>

          <el-row :gutter="20">
            <el-col :span="12">
              <h4 class="sub-title">已发现缺陷的模块</h4>
              <div v-if="coverageAssessment.covered_modules.length > 0" class="tag-group">
                <el-tag
                  v-for="mod in coverageAssessment.covered_modules"
                  :key="mod"
                  type="success"
                  class="module-tag"
                >
                  {{ mod }}
                </el-tag>
              </div>
              <el-empty v-else description="暂无" :image-size="40" />
            </el-col>
            <el-col :span="12">
              <h4 class="sub-title">未发现缺陷的模块</h4>
              <div v-if="coverageAssessment.uncovered_modules.length > 0" class="tag-group">
                <el-tag
                  v-for="mod in coverageAssessment.uncovered_modules"
                  :key="mod"
                  type="warning"
                  class="module-tag"
                >
                  {{ mod }}
                </el-tag>
              </div>
              <el-empty v-else description="所有模块均已覆盖" :image-size="40" />
            </el-col>
          </el-row>
        </el-card>

        <!-- ==================== 7. 用例执行摘要（折叠面板，非首屏） ==================== -->
        <el-card shadow="hover" class="mb-4">
          <el-collapse v-model="executionActiveNames">
            <el-collapse-item name="execution">
              <template #title>
                <span class="collapse-title">
                  用例执行摘要
                  <el-tag type="info" size="small" effect="plain">参考指标</el-tag>
                </span>
              </template>

              <el-row :gutter="16" class="mb-4">
                <el-col :span="4">
                  <div class="metric-item">
                    <span class="metric-label">用例总数</span>
                    <span class="metric-value">{{ report.total_cases }}</span>
                  </div>
                </el-col>
                <el-col :span="4">
                  <div class="metric-item">
                    <span class="metric-label">通过</span>
                    <span class="metric-value" style="color: #67c23a;">{{ report.passed_cases }}</span>
                  </div>
                </el-col>
                <el-col :span="4">
                  <div class="metric-item">
                    <span class="metric-label">失败</span>
                    <span class="metric-value" style="color: #f56c6c;">{{ report.failed_cases }}</span>
                  </div>
                </el-col>
                <el-col :span="4">
                  <div class="metric-item">
                    <span class="metric-label">阻塞</span>
                    <span class="metric-value" style="color: #e6a23c;">{{ report.blocked_cases }}</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="metric-item">
                    <span class="metric-label">通过率（参考指标）</span>
                    <span class="metric-value" style="color: #409eff;">
                      {{ report.pass_rate.toFixed(2) }}%
                    </span>
                  </div>
                </el-col>
              </el-row>

              <!-- 用例详情表格 -->
              <ReportTable
                :testCases="report.test_cases || []"
                :total="report.total_cases || 0"
                @pageChange="handlePageChange"
              />
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </div>

      <div v-else class="loading">
        <el-skeleton :rows="10" animated />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, nextTick, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElLoading } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { useReportStore } from '@/store/report'
import ReportTable from '@/components/report/ReportTable.vue'
import type {
  Report,
  DefectOverview,
  DefectItem,
  DefectDistribution,
  ImplicitDefects,
  SecurityFinding,
  CoverageAssessment,
  ReportContent,
} from '@/api/report'
import * as echarts from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import {
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsType } from 'echarts/core'

echarts.use([
  BarChart,
  PieChart,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  GridComponent,
  CanvasRenderer,
])

const route = useRoute()
const router = useRouter()
const reportStore = useReportStore()
const exportLoading = ref(false)

// ==================== 计算属性 ====================

const reportId = computed(() => {
  const id = Number(route.query.id)
  return isNaN(id) || id <= 0 ? 0 : id
})

const projectId = computed(() => {
  const id = Number(route.query.project_id)
  return isNaN(id) || id <= 0 ? 0 : id
})

const report = computed(() => reportStore.currentReport)

/** 从 report.content 安全提取缺陷维度数据 */
const reportContent = computed<ReportContent | null>(() => {
  const r = report.value as Report | null
  if (!r) return null
  // content 可能直接是对象，也可能在嵌套结构中
  const content = r.content
  if (content && typeof content === 'object' && 'defect_overview' in content) {
    return content as ReportContent
  }
  return null
})

const defectOverview = computed<DefectOverview | null>(() => {
  return reportContent.value?.defect_overview ?? null
})

const defectList = computed<DefectItem[]>(() => {
  return reportContent.value?.defect_list ?? []
})

/** 按 severity 升序排序（P0=1 置顶） */
const sortedDefectList = computed<DefectItem[]>(() => {
  const list = [...defectList.value]
  list.sort((a, b) => a.severity - b.severity)
  return list
})

const defectDistribution = computed<DefectDistribution | null>(() => {
  return reportContent.value?.defect_distribution ?? null
})

const implicitDefects = computed<ImplicitDefects | null>(() => {
  return reportContent.value?.implicit_defects ?? null
})

const hasImplicitDefects = computed(() => {
  const d = implicitDefects.value
  if (!d) return false
  return (
    d.console_errors.length > 0 ||
    d.network_failures.length > 0 ||
    d.memory_leaks.length > 0
  )
})

const securityFindings = computed<SecurityFinding[]>(() => {
  return reportContent.value?.security_findings ?? []
})

const coverageAssessment = computed<CoverageAssessment | null>(() => {
  return reportContent.value?.coverage_assessment ?? null
})

const coverageColor = computed(() => {
  const rate = coverageAssessment.value?.coverage_rate ?? 0
  if (rate >= 0.8) return '#67c23a'
  if (rate >= 0.5) return '#e6a23c'
  return '#f56c6c'
})

// ==================== 隐性缺陷折叠面板 ====================
const implicitActiveNames = ref<string[]>(['console', 'network', 'memory'])
const executionActiveNames = ref<string[]>([])

// ==================== 图表 ====================
const moduleChartRef = ref<HTMLElement>()
const categoryChartRef = ref<HTMLElement>()
let moduleChartInstance: EChartsType | null = null
let categoryChartInstance: EChartsType | null = null

/** 初始化模块分布横向柱状图 */
const initModuleChart = () => {
  if (!moduleChartRef.value || !defectDistribution.value) return
  moduleChartInstance = echarts.init(moduleChartRef.value)

  const data = defectDistribution.value.by_module
  const sortedData = [...data].sort((a, b) => a.count - b.count)

  moduleChartInstance.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '20%', right: '10%', top: '5%', bottom: '5%' },
    xAxis: { type: 'value' },
    yAxis: {
      type: 'category',
      data: sortedData.map((d) => d.module),
    },
    series: [
      {
        type: 'bar',
        data: sortedData.map((d) => d.count),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#f56c6c' },
            { offset: 1, color: '#e6a23c' },
          ]),
        },
        label: { show: true, position: 'right' },
      },
    ],
  })
}

/** 初始化缺陷类型饼图 */
const initCategoryChart = () => {
  if (!categoryChartRef.value || !defectDistribution.value) return
  categoryChartInstance = echarts.init(categoryChartRef.value)

  const data = defectDistribution.value.by_category
  const pieColors = ['#f56c6c', '#e6a23c', '#409eff', '#67c23a', '#909399', '#b37feb']

  categoryChartInstance.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 'middle' },
    series: [
      {
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['60%', '50%'],
        data: data.map((d, i) => ({
          name: d.category,
          value: d.count,
          itemStyle: { color: pieColors[i % pieColors.length] },
        })),
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
        label: { formatter: '{b}\n{d}%' },
      },
    ],
  })
}

/** 监听缺陷分布数据变化，初始化/更新图表 */
watch(
  () => defectDistribution.value,
  () => {
    nextTick(() => {
      if (defectDistribution.value) {
        if (!moduleChartInstance) {
          initModuleChart()
        } else {
          moduleChartInstance.resize()
        }
        if (!categoryChartInstance) {
          initCategoryChart()
        } else {
          categoryChartInstance.resize()
        }
      }
    })
  }
)

const handleResize = () => {
  moduleChartInstance?.resize()
  categoryChartInstance?.resize()
}

// ==================== 工具方法 ====================

/** 严重度 -> Tag 类型 */
const severityTagType = (severity: number): 'danger' | 'warning' | 'info' => {
  const map: Record<number, 'danger' | 'warning' | 'info'> = {
    1: 'danger',   // P0 致命
    2: 'danger',   // P1 严重
    3: 'warning',  // P2 一般
    4: 'info',     // P3 轻微
  }
  return map[severity] ?? 'info'
}

/** 严重度 -> 标签文本 */
const severityLabel = (severity: number): string => {
  const map: Record<number, string> = {
    1: 'P0 致命',
    2: 'P1 严重',
    3: 'P2 一般',
    4: 'P3 轻微',
  }
  return map[severity] ?? `P${severity}`
}

/** Bug 状态 -> Tag 类型 */
const bugStatusType = (status: string): 'danger' | 'warning' | 'success' | 'info' => {
  const map: Record<string, 'danger' | 'warning' | 'success' | 'info'> = {
    open: 'danger',
    in_progress: 'warning',
    fixed: 'success',
    closed: 'info',
    rejected: 'info',
  }
  return map[status] ?? 'info'
}

/** Bug 状态 -> 中文标签 */
const bugStatusLabel = (status: string): string => {
  const map: Record<string, string> = {
    open: '待处理',
    in_progress: '处理中',
    fixed: '已修复',
    closed: '已关闭',
    rejected: '已拒绝',
  }
  return map[status] ?? status
}

/** JSON 格式化展示 */
const formatJson = (obj: Record<string, unknown>): string => {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

// ==================== 导航与操作 ====================

const goBack = () => {
  router.push('/home/report')
}

const handlePageChange = (_page: number, _pageSize: number) => {}

const handleExportPDF = async () => {
  if (!reportId.value) return
  exportLoading.value = true
  try {
    const loadingInstance = ElLoading.service({
      lock: true,
      text: '正在导出PDF...',
      background: 'rgba(0, 0, 0, 0.7)',
    })
    const response = await reportStore.exportReportPDF(reportId.value, projectId.value)
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${report.value?.name || '测试报告'}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    loadingInstance.close()
    ElMessage.success('导出PDF成功')
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : '未知错误'
    ElMessage.error(`导出PDF失败: ${msg}`)
  } finally {
    exportLoading.value = false
  }
}

const handleExportHTML = async () => {
  if (!reportId.value) return
  exportLoading.value = true
  try {
    const loadingInstance = ElLoading.service({
      lock: true,
      text: '正在导出HTML...',
      background: 'rgba(0, 0, 0, 0.7)',
    })
    const response = await reportStore.exportReportHTML(reportId.value, projectId.value)
    const blob = new Blob([response.data], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${report.value?.name || '测试报告'}.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    loadingInstance.close()
    ElMessage.success('导出HTML成功')
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : '未知错误'
    ElMessage.error(`导出HTML失败: ${msg}`)
  } finally {
    exportLoading.value = false
  }
}

// ==================== 数据获取 ====================

const fetchReportDetail = async () => {
  if (!reportId.value) {
    ElMessage.error('报告ID无效')
    return
  }
  if (!projectId.value) {
    ElMessage.error('项目ID无效')
    return
  }
  try {
    await reportStore.fetchReportDetail(reportId.value, projectId.value)
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : '获取报告详情失败'
    ElMessage.error(msg)
  }
}

// ==================== 生命周期 ====================

onMounted(() => {
  fetchReportDetail()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  moduleChartInstance?.dispose()
  categoryChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.report-detail {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-content {
  margin-top: 20px;
}

.loading {
  margin-top: 20px;
}

.mb-3 {
  margin-bottom: 12px;
}

.mb-4 {
  margin-bottom: 20px;
}

/* 区域标题 */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

/* 统计卡片 */
.stat-card {
  text-align: center;
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-card--danger {
  border-left: 4px solid #f56c6c;
}

.stat-card--warning {
  border-left: 4px solid #e6a23c;
}

.stat-card--info {
  border-left: 4px solid #909399;
}

.stat-item {
  text-align: center;
  padding: 8px 0;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
}

.stat-card--danger .stat-value {
  color: #f56c6c;
}

.stat-card--warning .stat-value {
  color: #e6a23c;
}

.stat-card--info .stat-value {
  color: #909399;
}

/* 关键指标行 */
.metric-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 6px;
}

.metric-label {
  font-size: 13px;
  color: #909399;
  white-space: nowrap;
}

.metric-value {
  font-size: 22px;
  font-weight: bold;
  color: #303133;
}

.metric-unit {
  font-size: 12px;
  color: #c0c4cc;
}

/* 展开行 */
.expand-content {
  padding: 12px 20px;
}

.expand-section {
  margin-bottom: 12px;
}

.expand-section h4 {
  font-size: 14px;
  color: #606266;
  margin-bottom: 6px;
}

.expand-pre {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 10px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 图表 */
.chart-container {
  margin-top: 10px;
}

.chart-title {
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 8px;
  color: #606266;
}

.chart {
  width: 100%;
  height: 320px;
}

/* 折叠面板标题 */
.collapse-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: bold;
}

/* 安全发现详情 */
.security-detail p {
  margin: 4px 0;
  font-size: 13px;
}

/* 覆盖评估 */
.sub-title {
  font-size: 14px;
  font-weight: bold;
  color: #606266;
  margin-bottom: 10px;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.module-tag {
  margin: 0;
}
</style>
