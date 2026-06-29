<template>
    <el-card class="quick-assets-card" shadow="never">
        <template #header>
            <div class="card-title">生成资产</div>
        </template>

        <div class="assets-body">
            <!-- 自动创建的项目 -->
            <div class="asset-row">
                <span class="asset-label">关联项目</span>
                <span class="asset-value">{{ projectLabel }}</span>
            </div>

            <!-- 已存入用例数 -->
            <div class="asset-row">
                <span class="asset-label">已生成用例</span>
                <span class="asset-value">{{ caseCount }} 条</span>
            </div>

            <!-- 三套环境配置 -->
            <div v-if="hasEnvConfigs" class="env-section">
                <div class="section-title">环境配置</div>
                <div v-for="env in envList" :key="env.key" class="env-item">
                    <el-tag size="small" :type="env.tagType">{{ env.label }}</el-tag>
                    <span class="env-url">{{ env.url || '未配置' }}</span>
                </div>
            </div>

            <!-- 探索页面清单（可折叠） -->
            <el-collapse v-if="exploredPages.length > 0" class="explored-section">
                <el-collapse-item :title="`探索页面清单（${exploredPages.length}）`" name="explored">
                    <div v-for="(page, idx) in exploredPages" :key="idx" class="explored-item">
                        <el-icon class="page-icon"><Link /></el-icon>
                        <div class="page-info">
                            <div class="page-title">{{ page.title || page.url }}</div>
                            <div class="page-url">{{ page.url }}</div>
                        </div>
                        <el-image
                            v-if="page.screenshot"
                            :src="page.screenshot"
                            :preview-src-list="[page.screenshot]"
                            :preview-teleported="true"
                            fit="cover"
                            class="page-screenshot"
                        />
                    </div>
                </el-collapse-item>
            </el-collapse>
        </div>
    </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Link } from '@element-plus/icons-vue'
import projectApi from '@/api/project'
import type { WebEnvConfigs } from '@/api/project'

interface ExploredPage {
    url: string
    title?: string
    screenshot?: string
}

const props = defineProps<{
    projectId: number | null
    caseCount: number
    exploredPages: ExploredPage[]
}>()

const projectName = ref<string>('')
const envConfigs = ref<WebEnvConfigs | null>(null)

const projectLabel = computed(() => {
    if (projectName.value) return `${projectName.value} (#${props.projectId})`
    return props.projectId ? `项目 #${props.projectId}` : '-'
})

const envList = computed(() => {
    const cfg = envConfigs.value
    if (!cfg) return []
    return [
        { key: 'test', label: '测试', url: cfg.test?.url || '', tagType: 'success' as const },
        { key: 'staging', label: '灰度', url: cfg.staging?.url || '', tagType: 'warning' as const },
        { key: 'prod', label: '正式', url: cfg.prod?.url || '', tagType: 'danger' as const },
    ]
})

const hasEnvConfigs = computed(() => envList.value.some((e) => e.url))

onMounted(async () => {
    if (!props.projectId) return
    // 拉取项目名称 + 环境配置：失败时降级显示「项目 #{id}」
    try {
        const detail = (await projectApi.getProjectDetail(props.projectId)) as unknown as {
            data?: { name?: string; web_env_configs?: WebEnvConfigs }
        }
        projectName.value = detail?.data?.name || ''
        envConfigs.value = detail?.data?.web_env_configs || null
    } catch {
        // 降级：保留「项目 #{id}」展示
    }
    // 配置接口独立拉取（detail 可能不含完整 env 配置）
    try {
        const cfg = (await projectApi.getProjectConfig(props.projectId)) as unknown as {
            data?: { web_env_configs?: WebEnvConfigs }
        }
        if (cfg?.data?.web_env_configs) {
            envConfigs.value = cfg.data.web_env_configs
        }
    } catch {
        // 环境配置拉取失败不阻断
    }
})
</script>

<style scoped lang="scss">
.quick-assets-card {
    border: none;
    border-radius: 8px;
    height: 100%;
}

.card-title {
    font-size: 16px;
    font-weight: 700;
    color: #1f2d3d;
}

.assets-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.asset-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
}

.asset-label {
    color: #7a8594;
}

.asset-value {
    color: #1f2d3d;
    font-weight: 600;
}

.env-section {
    border-top: 1px dashed #e4e7ed;
    padding-top: 8px;
}

.section-title {
    font-size: 13px;
    font-weight: 600;
    color: #606266;
    margin-bottom: 6px;
}

.env-item {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}

.env-url {
    font-size: 12px;
    color: #606266;
    font-family: monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.explored-section {
    border-top: 1px dashed #e4e7ed;
    margin-top: 4px;
}

.explored-section :deep(.el-collapse-item__header) {
    font-size: 13px;
    font-weight: 600;
    color: #606266;
}

.explored-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    border-bottom: 1px solid #f0f2f5;
}

.page-icon {
    color: #909399;
    flex-shrink: 0;
}

.page-info {
    flex: 1;
    min-width: 0;
}

.page-title {
    font-size: 13px;
    color: #1f2d3d;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.page-url {
    font-size: 11px;
    color: #909399;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.page-screenshot {
    width: 60px;
    height: 40px;
    border-radius: 4px;
    border: 1px solid #e4e7ed;
    flex-shrink: 0;
    cursor: zoom-in;
}
</style>
