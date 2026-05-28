<template>
  <div class="lineage-tree">
    <div v-if="loading" class="lineage-loading">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-else-if="lineageError" class="lineage-error">
      <el-empty :description="lineageError" :image-size="60" />
    </div>

    <div v-else-if="lineageData" class="lineage-content">
      <div class="lineage-summary">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="根节点">
            <el-link type="primary" @click="navigateToCase(lineageData.root.id)">
              {{ lineageData.root.case_no }}
            </el-link>
          </el-descriptions-item>
          <el-descriptions-item label="链长度">
            <el-tag :type="lineageData.warning ? 'danger' : 'info'" size="small">
              {{ lineageData.chain_length }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="警告阈值">
            {{ lineageData.warning_threshold }}
          </el-descriptions-item>
        </el-descriptions>
        <el-alert
          v-if="lineageData.warning"
          type="warning"
          :closable="false"
          show-icon
          class="chain-warning"
        >
          <template #title>
            血缘链长度 {{ lineageData.chain_length }} 已达到警告阈值
            {{ lineageData.warning_threshold }}，建议拆分用例
          </template>
        </el-alert>
      </div>

      <div v-if="lineageData.ancestors.length > 0" class="ancestor-chain">
        <h4 class="sub-title">祖先链</h4>
        <div class="ancestor-list">
          <template v-for="(ancestor, index) in lineageData.ancestors" :key="ancestor.id">
            <div
              class="ancestor-item"
              :class="{ 'is-current': ancestor.id === props.caseId }"
              @click="navigateToCase(ancestor.id)"
            >
              <el-tag
                :type="getLifecycleTagType(ancestor.lifecycle_status)"
                size="small"
                class="status-tag"
              >
                {{ getLifecycleLabel(ancestor.lifecycle_status) }}
              </el-tag>
              <span class="ancestor-case-no">{{ ancestor.case_no }}</span>
              <span class="ancestor-title">{{ ancestor.title }}</span>
            </div>
            <el-icon v-if="index < lineageData.ancestors.length - 1" class="ancestor-arrow">
              <ArrowRight />
            </el-icon>
          </template>
        </div>
      </div>

      <div class="descendant-tree">
        <h4 class="sub-title">后代树</h4>
        <el-tree
          :data="treeData"
          :props="treeProps"
          node-key="id"
          default-expand-all
          :expand-on-click-node="false"
          :highlight-current="true"
          :current-node-key="props.caseId"
        >
          <template #default="{ data }">
            <div class="tree-node" @click="navigateToCase(data.id)">
              <el-tag
                :type="getLifecycleTagType(data.lifecycle_status)"
                size="small"
                class="status-tag"
              >
                {{ getLifecycleLabel(data.lifecycle_status) }}
              </el-tag>
              <span class="node-case-no">{{ data.case_no }}</span>
              <span class="node-title">{{ data.title }}</span>
              <el-tag
                v-if="data.id === props.caseId"
                type="primary"
                size="small"
                effect="dark"
                class="current-tag"
              >
                当前
              </el-tag>
            </div>
          </template>
        </el-tree>
      </div>
    </div>

    <div v-else class="lineage-empty">
      <el-empty description="暂无血缘关系数据" :image-size="60" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import { testCaseApi, type LineageResponse } from '@/api/case'
import type { TagType } from '@/types/element-plus'

const LIFECYCLE_MAP: Record<string, { label: string; tagType: TagType }> = {
  draft: { label: '草稿', tagType: 'info' },
  active: { label: '活跃', tagType: 'success' },
  pending_review: { label: '待评审', tagType: 'warning' },
  needs_modify: { label: '需修改', tagType: 'danger' },
  locator_broken: { label: '定位失效', tagType: 'danger' },
  deprecated: { label: '已废弃', tagType: 'info' },
  archived: { label: '已归档', tagType: 'info' },
}

const props = defineProps<{
  caseId: number
}>()

const router = useRouter()

const loading = ref(false)
const lineageData = ref<LineageResponse | null>(null)
const lineageError = ref<string>('')

const treeData = computed(() => {
  if (!lineageData.value) return []
  return [lineageData.value.root]
})

const treeProps = {
  children: 'children',
  label: 'case_no',
}

function getLifecycleLabel(status: string): string {
  return LIFECYCLE_MAP[status]?.label ?? status
}

function getLifecycleTagType(status: string): TagType {
  return LIFECYCLE_MAP[status]?.tagType ?? 'info'
}

function navigateToCase(caseId: number): void {
  if (caseId === props.caseId) return
  router.push({ name: 'CaseDetail', params: { caseId: String(caseId) } })
}

async function fetchLineage(): Promise<void> {
  if (!props.caseId) return
  loading.value = true
  lineageError.value = ''
  try {
    lineageData.value = await testCaseApi.getLineage(props.caseId)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    lineageError.value = `加载血缘数据失败: ${msg}`
    lineageData.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchLineage()
})

watch(
  () => props.caseId,
  () => {
    fetchLineage()
  }
)

defineExpose({ refresh: fetchLineage })
</script>

<style scoped>
.lineage-tree {
  padding: 0;
}

.lineage-loading,
.lineage-error,
.lineage-empty {
  padding: 20px;
  text-align: center;
}

.lineage-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.lineage-summary {
  margin-bottom: 4px;
}

.chain-warning {
  margin-top: 8px;
}

.sub-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px 0;
}

.ancestor-chain {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
}

.ancestor-list {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.ancestor-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
  font-size: 13px;
}

.ancestor-item:hover {
  background-color: #ecf5ff;
}

.ancestor-item.is-current {
  background-color: #409eff;
  color: #fff;
}

.ancestor-item.is-current .ancestor-case-no,
.ancestor-item.is-current .ancestor-title {
  color: #fff;
}

.ancestor-arrow {
  color: #c0c4cc;
  font-size: 12px;
}

.ancestor-case-no,
.node-case-no {
  font-family: 'Courier New', monospace;
  font-weight: 600;
  color: #606266;
  font-size: 13px;
}

.ancestor-title,
.node-title {
  color: #909399;
  font-size: 13px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.descendant-tree {
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}

.tree-node {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 2px 0;
}

.tree-node:hover .node-case-no {
  color: #409eff;
}

.status-tag {
  flex-shrink: 0;
}

.current-tag {
  flex-shrink: 0;
  margin-left: 4px;
}

:deep(.el-tree-node__content) {
  height: 32px;
}

:deep(.el-tree-node.is-current > .el-tree-node__content) {
  background-color: #ecf5ff;
}
</style>
