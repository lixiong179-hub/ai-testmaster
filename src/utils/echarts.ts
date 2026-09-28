/**
 * ECharts 按需引入统一入口
 *
 * 设计目的：
 * 1. 消除 usePipelineDashboard / useAICostDashboard / ReportDetail / ReportStat 四处重复的 echarts.use([...]) 注册代码
 * 2. 集中管理图表与组件依赖，新增图表类型只需在此处追加，避免遗漏注册导致运行时报错
 * 3. 保留按需引入优势：仅打包实际使用的图表/组件，相比 `import * as echarts from 'echarts'` 可显著减小体积
 *
 * 使用方式：
 *   import { echarts, type EChartsType } from '@/utils/echarts'
 */
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// 注册所有业务用到的图表与组件（union of 4 个原调用点的依赖）
echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  CanvasRenderer,
])

export { echarts }
export type EChartsType = echarts.EChartsType
export default echarts
