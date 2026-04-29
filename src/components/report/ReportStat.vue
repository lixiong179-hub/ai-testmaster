<template>
  <div class="report-stat">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>测试统计</span>
        </div>
      </template>
      
      <div class="stats-container">
        <!-- 统计卡片 -->
        <el-row :gutter="20" class="mb-4">
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-label">总用例数</div>
                <div class="stat-value">{{ report?.total_cases || 0 }}</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-label">通过用例</div>
                <div class="stat-value success">{{ report?.passed_cases || 0 }}</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-label">失败用例</div>
                <div class="stat-value danger">{{ report?.failed_cases || 0 }}</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-label">通过率</div>
                <div class="stat-value warning">{{ (report?.pass_rate || 0).toFixed(2) }}%</div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        
        <!-- 图表区域 -->
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="chart-container">
              <h4 class="chart-title">执行结果分布</h4>
              <div ref="pieChart" class="chart"></div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="chart-container">
              <h4 class="chart-title">通过率趋势</h4>
              <div ref="lineChart" class="chart"></div>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { Report } from '@/api/report'

const props = defineProps<{
  report: Report | null
}>()

const pieChart = ref<HTMLElement>()
const lineChart = ref<HTMLElement>()
let pieChartInstance: echarts.ECharts | null = null
let lineChartInstance: echarts.ECharts | null = null

// 初始化饼图
const initPieChart = () => {
  if (!pieChart.value) return
  
  pieChartInstance = echarts.init(pieChart.value)
  updatePieChart()
}

// 更新饼图
const updatePieChart = () => {
  if (!pieChartInstance || !props.report) return
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: '执行结果',
        type: 'pie',
        radius: '50%',
        data: [
          { value: props.report.passed_cases, name: '通过', itemStyle: { color: '#67c23a' } },
          { value: props.report.failed_cases, name: '失败', itemStyle: { color: '#f56c6c' } },
          { value: props.report.total_cases - props.report.passed_cases - props.report.failed_cases, name: '其他', itemStyle: { color: '#909399' } }
        ],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
  
  pieChartInstance.setOption(option)
}

// 初始化折线图
const initLineChart = () => {
  if (!lineChart.value) return
  
  lineChartInstance = echarts.init(lineChart.value)
  updateLineChart()
}

// 更新折线图
const updateLineChart = () => {
  if (!lineChartInstance || !props.report) return
  
  // 模拟通过率趋势数据
  const mockData = [
    { name: '第1轮', value: 75 },
    { name: '第2轮', value: 80 },
    { name: '第3轮', value: 85 },
    { name: '第4轮', value: 90 },
    { name: '第5轮', value: props.report.pass_rate }
  ]
  
  const option = {
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: mockData.map(item => item.name)
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [
      {
        data: mockData.map(item => item.value),
        type: 'line',
        smooth: true,
        itemStyle: {
          color: '#409eff'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            {
              offset: 0,
              color: 'rgba(64, 158, 255, 0.5)'
            },
            {
              offset: 1,
              color: 'rgba(64, 158, 255, 0.1)'
            }
          ])
        }
      }
    ]
  }
  
  lineChartInstance.setOption(option)
}

// 监听报告数据变化
watch(() => props.report, () => {
  nextTick(() => {
    updatePieChart()
    updateLineChart()
  })
}, { deep: true })

// 监听窗口大小变化
const handleResize = () => {
  pieChartInstance?.resize()
  lineChartInstance?.resize()
}

onMounted(() => {
  initPieChart()
  initLineChart()
  window.addEventListener('resize', handleResize)
})

// 组件卸载时销毁图表
onUnmounted(() => {
  pieChartInstance?.dispose()
  lineChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.report-stat {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-container {
  margin-top: 20px;
}

.mb-4 {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
}

.stat-value.success {
  color: #67c23a;
}

.stat-value.danger {
  color: #f56c6c;
}

.stat-value.warning {
  color: #e6a23c;
}

.chart-container {
  margin-top: 20px;
}

.chart-title {
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 10px;
  color: #303133;
}

.chart {
  width: 100%;
  height: 300px;
}
</style>
