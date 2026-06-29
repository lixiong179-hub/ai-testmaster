<template>
    <div class="quick-result-view">
        <!-- 11.9 失败降级提示区（phase=failed 时置顶） -->
        <el-alert
            v-if="exploreFailed"
            type="error"
            :closable="false"
            title="无法访问该网址，请检查 URL 或网络"
            show-icon
            class="degrade-alert"
        >
            <el-button type="primary" size="small" @click="emit('rerun')">重试 / 换网址</el-button>
        </el-alert>
        <el-alert
            v-else-if="loginFailed"
            type="warning"
            :closable="false"
            title="登录凭据无效，是否以未登录状态继续探索？"
            show-icon
            class="degrade-alert"
        >
            <el-button size="small" @click="emit('rerun')">重新输入凭据</el-button>
        </el-alert>
        <el-alert
            v-else-if="aiFailed"
            type="warning"
            :closable="false"
            title="AI 服务暂时不可用，已降级生成基础登录用例"
            show-icon
            class="degrade-alert"
        />
        <el-alert
            v-if="store.isFailed && store.errorMessage"
            type="error"
            :closable="false"
            :title="store.errorMessage"
            show-icon
            class="degrade-alert"
        />

        <!-- 用例超时计数提示 -->
        <div v-if="timeoutCount > 0" class="timeout-hint">{{ timeoutCount }} 条用例超时</div>

        <!-- 5 区块网格：桌面三列 / 平板两列 -->
        <el-row :gutter="16" class="result-grid">
            <!-- 区块 1 报告摘要 -->
            <el-col :xs="24" :sm="12" :lg="8">
                <QuickSummaryCard :summary="summary" />
            </el-col>

            <!-- 区块 4 生成资产 -->
            <el-col :xs="24" :sm="12" :lg="8">
                <QuickAssetsCard
                    :project-id="store.projectId"
                    :case-count="store.caseCount"
                    :explored-pages="exploredPages"
                />
            </el-col>

            <!-- 区块 3 缺陷清单 -->
            <el-col :xs="24" :sm="12" :lg="8">
                <QuickDefectList :defects="defects" @create-bug="onCreateBug" />
            </el-col>

            <!-- 区块 2 用例列表（占整行） -->
            <el-col :span="24">
                <el-card class="case-list-card" shadow="never">
                    <template #header>
                        <div class="case-list-header">
                            <span class="card-title">用例列表</span>
                            <el-radio-group v-model="caseFilter" size="small">
                                <el-radio-button value="all">全部 ({{ cases.length }})</el-radio-button>
                                <el-radio-button value="passed">通过 ({{ passedCount }})</el-radio-button>
                                <el-radio-button value="failed">失败 ({{ failedCount }})</el-radio-button>
                            </el-radio-group>
                        </div>
                    </template>
                    <div v-if="filteredCases.length > 0" class="case-list">
                        <CaseCard v-for="c in filteredCases" :key="c.id" :case-data="c" />
                    </div>
                    <el-empty v-else description="暂无用例数据，请查看完整报告" :image-size="80">
                        <el-button type="primary" @click="emit('view-report')">查看完整报告</el-button>
                    </el-empty>
                </el-card>
            </el-col>

            <!-- 区块 5 操作按钮区（占整行） -->
            <el-col :span="24">
                <el-card class="actions-card" shadow="never">
                    <div class="actions-body">
                        <el-button type="primary" @click="emit('view-report')">查看完整报告</el-button>
                        <el-button @click="emit('rerun')">再次执行</el-button>
                        <el-button @click="emit('edit-cases')">编辑用例</el-button>
                        <el-dropdown @command="onDownload" trigger="click">
                            <el-button>下载报告<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                            <template #dropdown>
                                <el-dropdown-menu>
                                    <el-dropdown-item command="pdf">PDF</el-dropdown-item>
                                    <el-dropdown-item command="html">HTML</el-dropdown-item>
                                </el-dropdown-menu>
                            </template>
                        </el-dropdown>
                        <el-button @click="openSaveDialog">保存到其他项目</el-button>
                    </div>
                </el-card>
            </el-col>
        </el-row>

        <!-- 保存到其他项目对话框 -->
        <el-dialog v-model="saveDialogVisible" title="保存到其他项目" width="480px">
            <el-select
                v-model="targetProjectId"
                placeholder="选择目标项目"
                filterable
                :loading="projectLoading"
                style="width: 100%"
            >
                <el-option
                    v-for="p in projectOptions"
                    :key="p.id"
                    :label="`${p.name} (#${p.id})`"
                    :value="p.id"
                />
            </el-select>
            <template #footer>
                <el-button @click="saveDialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="saving" @click="confirmSave">保存</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useQuickTestStore } from '@/store/quickTest'
import projectApi from '@/api/project'
import type { CaseData, DefectData, SummaryStats, QuickTestResultDetail } from '../quickTestTypes'
import QuickSummaryCard from './QuickSummaryCard.vue'
import QuickAssetsCard from './QuickAssetsCard.vue'
import QuickDefectList from './QuickDefectList.vue'
import CaseCard from './CaseCard.vue'

type ExploredPage = NonNullable<QuickTestResultDetail['explored_pages']>[number]

const props = defineProps<{
    resultDetail: QuickTestResultDetail | null
    cases: CaseData[]
    defects: DefectData[]
    summary: SummaryStats | null
    exploredPages: ExploredPage[]
}>()

const emit = defineEmits<{
    (e: 'view-report'): void
    (e: 'edit-cases'): void
    (e: 'download', format: 'pdf' | 'html'): void
    (e: 'save-to-project', targetProjectId: number): void
    (e: 'rerun'): void
    (e: 'fetch-report'): void
}>()

const store = useQuickTestStore()
const caseFilter = ref<'all' | 'passed' | 'failed'>('all')

const passedCount = computed(() => props.cases.filter((c) => c.status === 'passed').length)
const failedCount = computed(() => props.cases.filter((c) => c.status === 'failed').length)

const filteredCases = computed(() => {
    if (caseFilter.value === 'all') return props.cases
    return props.cases.filter((c) => c.status === caseFilter.value)
})

// 11.9 失败降级判定
const exploreFailed = computed(
    () => store.isFailed && store.currentStage === 'site_exploring'
)
const loginFailed = computed(
    () => store.isFailed && (store.errorMessage || '').includes('登录')
)
const aiFailed = computed(
    () => store.isFailed && /AI|降级/.test(store.errorMessage || '')
)
const timeoutCount = computed(
    () => props.cases.filter((c) => (c.failure_reason || '').includes('超时')).length
)

// 保存到其他项目对话框
const saveDialogVisible = ref(false)
const targetProjectId = ref<number | null>(null)
const projectOptions = ref<Array<{ id: number; name: string }>>([])
const projectLoading = ref(false)
const saving = ref(false)

async function openSaveDialog(): Promise<void> {
    saveDialogVisible.value = true
    targetProjectId.value = null
    if (projectOptions.value.length > 0) return
    projectLoading.value = true
    try {
        const res = (await projectApi.getProjects({ page: 1, page_size: 200 })) as unknown as {
            data?: { items?: Array<{ id: number; name: string }> }
        }
        const items = res?.data?.items || []
        // 排除当前项目自身
        projectOptions.value = items.filter((p) => p.id !== store.projectId)
    } catch {
        ElMessage.info('保存到其他项目入口即将上线')
    } finally {
        projectLoading.value = false
    }
}

async function confirmSave(): Promise<void> {
    if (!targetProjectId.value) {
        ElMessage.warning('请选择目标项目')
        return
    }
    saving.value = true
    try {
        emit('save-to-project', targetProjectId.value)
        saveDialogVisible.value = false
    } finally {
        saving.value = false
    }
}

function onDownload(format: string): void {
    emit('download', format as 'pdf' | 'html')
}

function onCreateBug(_defect: DefectData): void {
    // 创建 Bug 入口尚未落地：由 QuickDefectList 本地兜底提示，此处仅预留扩展点
}

onMounted(() => {
    // restore 后无 WS 推送明细时，主动拉取报告补齐用例/缺陷数据
    if (props.cases.length === 0 && store.taskId) {
        emit('fetch-report')
    }
})
</script>

<style scoped lang="scss">
.quick-result-view {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.degrade-alert {
    border-radius: 8px;
}

.timeout-hint {
    color: #e6a23c;
    font-size: 13px;
    padding: 6px 12px;
    background: #fdf6ec;
    border-radius: 4px;
}

.result-grid {
    row-gap: 16px;
}

.case-list-card,
.actions-card {
    border: none;
    border-radius: 8px;
}

.card-title {
    font-size: 16px;
    font-weight: 700;
    color: #1f2d3d;
}

.case-list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.case-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 12px;
}

.actions-body {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

@media (max-width: 768px) {
    .case-list {
        grid-template-columns: 1fr;
    }
    .case-list-header {
        flex-direction: column;
        align-items: stretch;
    }
}
</style>
