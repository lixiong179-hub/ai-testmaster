<template>
  <div class="test-point-extract-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2>测试点提取</h2>
        <div class="step-nav-buttons" v-if="currentStep > 0 || currentStep < 3">
          <el-button 
            :disabled="currentStep === 0" 
            @click="goToPrevStep"
            round
            plain
            size="small"
          >
            <el-icon><ArrowLeft /></el-icon>
            上一步
          </el-button>
          <el-button 
            :disabled="currentStep === 3" 
            @click="goToNextStep"
            type="primary"
            round
            size="small"
          >
            下一步
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>
      <el-button @click="handleBack">
        <el-icon><ArrowLeft /></el-icon>
        返回列表
      </el-button>
    </div>

    <!-- 步骤条 -->
    <div class="steps-wrapper steps-enhanced">
      <el-steps :active="currentStep" finish-status="success" align-center class="custom-steps">
        <el-step title="选择项目" description="选择目标项目">
          <template #icon>
            <div class="step-icon-custom">
              <el-icon><FolderOpened /></el-icon>
            </div>
          </template>
        </el-step>
        <el-step title="选择需求" description="选择需求资源">
          <template #icon>
            <div class="step-icon-custom">
              <el-icon><Document /></el-icon>
            </div>
          </template>
        </el-step>
        <el-step title="AI提取" description="提取测试点">
          <template #icon>
            <div class="step-icon-custom">
              <el-icon><MagicStick /></el-icon>
            </div>
          </template>
        </el-step>
        <el-step title="管理测试点" description="编辑与管理">
          <template #icon>
            <div class="step-icon-custom">
              <el-icon><List /></el-icon>
            </div>
          </template>
        </el-step>
      </el-steps>
    </div>

    <!-- 主内容区：左右分栏 -->
    <div class="main-content">
      <!-- 左侧：操作区 -->
      <div class="left-panel">
        <transition name="slide-fade" mode="out-in">
        <!-- 步骤1：选择项目 -->
          <div v-if="currentStep === 0" key="step1" class="step-content">
            <div class="step-title step-title-gradient">
              <el-icon><FolderOpened /></el-icon>
              <span>选择项目</span>
              <span class="step-badge">1/4</span>
            </div>
            <div class="step-body step-body-enhanced">
              <!-- 未选择项目时的引导界面 -->
              <div v-if="!formData.project_id" class="project-selection-guide">
                <div class="guide-illustration">
                  <div class="illustration-circle">
                    <el-icon :size="64" color="#409EFF"><FolderOpened /></el-icon>
                  </div>
                  <div class="floating-icons">
                    <div class="float-icon float-1"><el-icon :size="24"><Document /></el-icon></div>
                    <div class="float-icon float-2"><el-icon :size="20"><MagicStick /></el-icon></div>
                    <div class="float-icon float-3"><el-icon :size="22"><DataAnalysis /></el-icon></div>
                  </div>
                </div>
                <div class="guide-content">
                  <h3 class="guide-title">选择您的项目</h3>
                  <p class="guide-description">选择一个项目后，AI将帮助您自动提取测试点，提升测试效率</p>
                </div>
                <div class="project-select-enhanced">
                  <el-select
                    v-model="formData.project_id"
                    placeholder="请搜索或选择项目"
                    size="large"
                    filterable
                    clearable
                    style="width: 100%"
                    @change="handleProjectChange"
                  >
                    <template #prefix>
                      <el-icon><Search /></el-icon>
                    </template>
                    <el-option
                      v-for="project in projects"
                      :key="project.id"
                      :label="project.name"
                      :value="project.id"
                    >
                      <div class="project-option">
                        <el-icon><FolderOpened /></el-icon>
                        <span>{{ project.name }}</span>
                      </div>
                    </el-option>
                  </el-select>
                </div>
                <div class="workflow-hint">
                  <div class="workflow-steps">
                    <div class="wf-step">
                      <div class="wf-number">1</div>
                      <span>选择项目</span>
                    </div>
                    <div class="wf-arrow"><el-icon><ArrowRight /></el-icon></div>
                    <div class="wf-step">
                      <div class="wf-number">2</div>
                      <span>上传需求</span>
                    </div>
                    <div class="wf-arrow"><el-icon><ArrowRight /></el-icon></div>
                    <div class="wf-step">
                      <div class="wf-number">3</div>
                      <span>AI提取</span>
                    </div>
                    <div class="wf-arrow"><el-icon><ArrowRight /></el-icon></div>
                    <div class="wf-step">
                      <div class="wf-number">4</div>
                      <span>管理测试点</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 已选择项目后的展示 -->
              <div v-else class="project-selected-view">
                <div class="selected-project-card">
                  <div class="project-card-header">
                    <div class="project-icon-large">
                      <el-icon :size="48"><FolderOpened /></el-icon>
                    </div>
                    <div class="project-info-main">
                      <h3 class="project-name-large">{{ selectedProjectInfo?.name }}</h3>
                      <div class="project-meta-tags">
                        <el-tag type="primary" effect="plain" size="small">ID: {{ selectedProjectInfo?.id }}</el-tag>
                        <el-tag type="success" effect="plain" size="small">{{ files.length }} 个资源文件</el-tag>
                      </div>
                    </div>
                  </div>
                  <div class="project-card-body">
                    <div class="info-grid">
                      <div class="grid-item">
                        <div class="grid-icon"><el-icon :size="28" color="#409EFF"><Files /></el-icon></div>
                        <div class="grid-content">
                          <div class="grid-value">{{ files.length }}</div>
                          <div class="grid-label">资源文件</div>
                        </div>
                      </div>
                      <div class="grid-item">
                        <div class="grid-icon"><el-icon :size="28" color="#67C23A"><Document /></el-icon></div>
                        <div class="grid-content">
                          <div class="grid-value">{{ getResourceTypeCount('requirement') }}</div>
                          <div class="grid-label">需求文档</div>
                        </div>
                      </div>
                      <div class="grid-item">
                        <div class="grid-icon"><el-icon :size="28" color="#E6A23C"><Picture /></el-icon></div>
                        <div class="grid-content">
                          <div class="grid-value">{{ getResourceTypeCount('ui_mockup') }}</div>
                          <div class="grid-label">UI原型</div>
                        </div>
                      </div>
                      <div class="grid-item">
                        <div class="grid-icon"><el-icon :size="28" color="#F56C6C"><DocumentCopy /></el-icon></div>
                        <div class="grid-content">
                          <div class="grid-value">{{ getResourceTypeCount('api_doc') }}</div>
                          <div class="grid-label">API文档</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="project-card-footer">
                    <el-button size="large" @click="formData.project_id = '' as number | ''">
                      <el-icon><RefreshLeft /></el-icon>
                      重新选择
                    </el-button>
                    <el-button type="primary" size="large" @click="goToNextStep">
                      下一步：选择需求
                      <el-icon><ArrowRight /></el-icon>
                    </el-button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 步骤2：选择需求资源 -->
          <div v-else-if="currentStep === 1" key="step2" class="step-content">
            <div class="step-title">
              <el-icon><Document /></el-icon>
              <span>选择需求资源</span>
            </div>
            <div class="step-body">
              <!-- 资源类型筛选 -->
              <div class="filter-bar">
                <el-radio-group v-model="resourceTypeFilter" size="small">
                  <el-radio-button value="">全部</el-radio-button>
                  <el-radio-button value="requirement">需求文档</el-radio-button>
                  <el-radio-button value="ui_mockup">UI原型</el-radio-button>
                  <el-radio-button value="api_doc">API文档</el-radio-button>
                </el-radio-group>
              </div>

              <!-- 资源列表 -->
              <div v-if="filteredResourceRows.length > 0" class="resource-list">
                <div
                  v-for="resource in filteredResourceRows"
                  :key="resource.id"
                  class="resource-item"
                  :class="{ active: selectedResource?.id === resource.id }"
                  @click="handleResourceSelect(resource)"
                >
                  <div class="resource-icon">
                    <el-icon :size="24">
                      <component :is="getResourceIcon(resource.resource_type)" />
                    </el-icon>
                  </div>
                  <div class="resource-info">
                    <div class="resource-name">{{ resource.display_name }}</div>
                    <div class="resource-meta">
                      <el-tag size="small" :type="getResourceTypeTagType(resource.resource_type)">
                        {{ getResourceTypeLabel(resource.resource_type) }}
                      </el-tag>
                      <span class="resource-size">{{ resource.size_text }}</span>
                      <span class="resource-time">{{ resource.time_text }}</span>
                    </div>
                  </div>
                  <div class="resource-action">
                    <el-button type="primary" size="small" @click.stop="goToExtract(resource)">
                      提取测试点
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-else class="empty-hint">
                <el-empty description="该项目暂无上传文件，请先在「资源管理」中添加" :image-size="120" />
              </div>
            </div>
          </div>

          <!-- 步骤3：AI提取测试点 -->
          <div v-else-if="currentStep === 2" key="step3" class="step-content">
            <div class="step-title">
              <el-icon><MagicStick /></el-icon>
              <span>AI提取测试点</span>
            </div>
            <div class="step-body">
              <!-- 已选资源信息 -->
              <div v-if="selectedResource" class="selected-resource-card">
                <div class="resource-summary">
                  <el-icon :size="32"><component :is="getResourceIcon(selectedResource.resource_type)" /></el-icon>
                  <div>
                    <div class="resource-name">{{ selectedResource.display_name }}</div>
                    <div class="resource-meta">{{ selectedResource.type_label }} · {{ selectedResource.size_text }}</div>
                  </div>
                </div>
              </div>

              <!-- 提取进度 - 骨架屏 -->
              <div v-if="extracting" class="extract-progress">
                <div class="skeleton-wrapper">
                  <el-skeleton :rows="5" animated />
                </div>
                <div class="progress-section">
                  <el-progress
                    :percentage="progress"
                    :status="progressStatus"
                    :stroke-width="16"
                    :text-inside="true"
                  />
                  <div class="progress-text-animated">{{ progressText }}</div>
                  <el-button type="danger" plain @click="handleCancel" size="small">
                    <el-icon><Close /></el-icon>
                    取消提取
                  </el-button>
                </div>
              </div>

              <!-- 提取完成/错误状态 -->
              <div v-else-if="errorMessage" class="extract-error">
                <el-result icon="error" title="提取失败" :sub-title="errorMessage">
                  <template #extra>
                    <el-button type="primary" @click="retryExtract">
                      <el-icon><Refresh /></el-icon>
                      重试
                    </el-button>
                  </template>
                </el-result>
              </div>

              <!-- 提取成功 -->
              <div v-else-if="testPoints.length > 0" class="extract-success">
                <div class="success-header">
                  <div class="success-icon-wrapper">
                    <el-icon :size="48" color="#67C23A"><CircleCheckFilled /></el-icon>
                  </div>
                  <div class="success-info">
                    <h3 class="success-title">提取成功！</h3>
                    <p class="success-desc">共提取 <strong>{{ testPoints.length }}</strong> 个测试点</p>
                  </div>
                </div>
                <div class="success-stats-grid">
                  <div class="stat-item stat-high">
                    <span class="stat-number">{{ getPriorityCount(0) }}</span>
                    <span class="stat-label">高优先级</span>
                  </div>
                  <div class="stat-item stat-medium">
                    <span class="stat-number">{{ getPriorityCount(1) }}</span>
                    <span class="stat-label">中优先级</span>
                  </div>
                  <div class="stat-item stat-low">
                    <span class="stat-number">{{ getPriorityCount(2) }}</span>
                    <span class="stat-label">低优先级</span>
                  </div>
                  <div class="stat-item stat-modules">
                    <span class="stat-number">{{ moduleCount }}</span>
                    <span class="stat-label">模块数</span>
                  </div>
                </div>
                <div class="success-actions">
                  <el-button type="primary" size="large" @click="goToNextStep">
                    下一步：管理测试点
                    <el-icon><ArrowRight /></el-icon>
                  </el-button>
                  <el-button size="large" @click="retryExtract" plain>
                    <el-icon><Refresh /></el-icon>
                    重新提取
                  </el-button>
                </div>
              </div>

              <!-- 等待提取 -->
              <div v-else class="extract-ready">
                <el-empty description="点击下方按钮开始AI提取测试点" :image-size="120">
                  <template #image>
                    <div class="ready-icon">
                      <el-icon :size="80" color="#409EFF"><MagicStick /></el-icon>
                    </div>
                  </template>
                  <template #description>
                    <p class="ready-text">AI将自动分析需求文档并提取测试点</p>
                  </template>
                  <template #default>
                    <el-button type="primary" size="large" @click="startExtract" :disabled="!selectedResource">
                      <el-icon><MagicStick /></el-icon>
                      开始提取
                    </el-button>
                  </template>
                </el-empty>
              </div>
            </div>
          </div>

          <!-- 步骤4：管理测试点 -->
          <div v-else-if="currentStep === 3" key="step4" class="step-content step-full">
            <div class="step-title">
              <el-icon><List /></el-icon>
              <span>管理测试点 (共{{ savedFromDb ? dbTotal : testPoints.length }}个)</span>
            </div>
            <div class="step-body">
              <!-- 批量操作工具栏 -->
              <div v-if="selectedRows.length > 0 || testPoints.length > 0" class="batch-toolbar">
                <div v-if="selectedRows.length > 0" class="batch-info">
                  <el-alert
                    :title="`已选择 ${selectedRows.length} 个测试点`"
                    type="info"
                    :closable="false"
                    show-icon
                  />
                  <el-button type="danger" size="small" @click="batchDeleteTestPoints" :loading="batchDeleting">
                    <el-icon><Delete /></el-icon>
                    批量删除
                  </el-button>
                  <el-button size="small" @click="clearSelection">取消选择</el-button>
                </div>
                <div class="action-buttons">
                  <el-button type="success" @click="saveToDatabase" :loading="saving">
                    <el-icon><Check /></el-icon>
                    保存用例
                  </el-button>
                  <el-button type="primary" @click="generateTestCases">
                    <el-icon><MagicStick /></el-icon>
                    生成测试用例
                  </el-button>
                </div>
              </div>

              <!-- 测试点表格 -->
              <div v-if="paginatedTestPoints.length > 0" class="table-wrapper">
                <el-table
                  ref="testPointTable"
                  :data="paginatedTestPoints"
                  border
                  stripe
                  highlight-current-row
                  @selection-change="handleSelectionChange"
                  v-loading="loadingTestPoints"
                  empty-text="暂无测试点数据"
                  style="width: 100%"
                >
                  <el-table-column type="selection" width="50" fixed="left" />
                  <el-table-column prop="id" label="ID" width="72" />
                  <el-table-column prop="module" label="模块" width="120" />
                  <el-table-column prop="function" label="功能" width="160" />
                  <el-table-column prop="point" label="测试点描述" min-width="200" />
                  <el-table-column prop="priority" label="优先级" width="100">
                    <template #default="scope">
                      <el-tag :type="getPriorityTagType(scope.row.priority)">
                        {{ getPriorityLabel(scope.row.priority) }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="180" fixed="right">
                    <template #default="{ row }">
                      <el-button type="primary" size="small" @click="editTestPoint(row)" :loading="updating">
                        <el-icon><Edit /></el-icon>编辑
                      </el-button>
                      <el-popconfirm title="确定删除此测试点？" @confirm="deleteTestPoint(row)">
                        <template #reference>
                          <el-button type="danger" size="small" :disabled="deleting">
                            <el-icon><Delete /></el-icon>删除
                          </el-button>
                        </template>
                      </el-popconfirm>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- 分页 -->
                <div class="pagination-wrapper" v-if="(savedFromDb && dbTotal > pageSize) || (!savedFromDb && testPoints.length > pageSize)">
                  <el-pagination
                    v-model:current-page="currentPage"
                    :page-size="pageSize"
                    :total="savedFromDb ? dbTotal : testPoints.length"
                    layout="total, prev, pager, next, jumper"
                    @current-change="handlePageChange"
                  />
                </div>
              </div>

              <!-- 空状态 -->
              <div v-else class="empty-hint">
                <el-empty description="暂无测试点数据，请先提取测试点" :image-size="120">
                  <template #image>
                    <div class="empty-icon">
                      <el-icon :size="80" color="#C0C4CC"><Document /></el-icon>
                    </div>
                  </template>
                </el-empty>
              </div>
            </div>
          </div>
        </transition>
      </div>

      <!-- 右侧：预览/摘要面板 -->
      <div class="right-panel right-panel-enhanced">
        <transition name="fade" mode="out-in">
          <!-- 步骤1右侧：项目摘要/工作流程指引 -->
          <div v-if="currentStep === 0" key="preview1" class="preview-card preview-card-enhanced">
            <div v-if="!selectedProjectInfo" class="preview-welcome">
              <div class="welcome-illustration">
                <div class="welcome-icon-bg">
                  <el-icon :size="56" color="#fff"><MagicStick /></el-icon>
                </div>
              </div>
              <h3 class="welcome-title">AI 智能测试点提取</h3>
              <p class="welcome-desc">基于人工智能技术，自动从需求文档中提取测试点</p>
              
              <div class="feature-list">
                <div class="feature-item">
                  <div class="feature-icon"><el-icon :size="20" color="#409EFF"><Document /></el-icon></div>
                  <div class="feature-text">
                    <div class="feature-name">智能解析</div>
                    <div class="feature-desc">自动识别需求文档结构</div>
                  </div>
                </div>
                <div class="feature-item">
                  <div class="feature-icon"><el-icon :size="20" color="#67C23A"><MagicStick /></el-icon></div>
                  <div class="feature-text">
                    <div class="feature-name">AI 提取</div>
                    <div class="feature-desc">智能生成测试点</div>
                  </div>
                </div>
                <div class="feature-item">
                  <div class="feature-icon"><el-icon :size="20" color="#E6A23C"><DataAnalysis /></el-icon></div>
                  <div class="feature-text">
                    <div class="feature-name">数据分析</div>
                    <div class="feature-desc">多维度统计分析</div>
                  </div>
                </div>
              </div>

              <div class="tip-card">
                <el-icon :size="18" color="#E6A23C"><InfoFilled /></el-icon>
                <span>请先从左侧选择一个项目开始</span>
              </div>
            </div>

            <div v-else class="preview-body preview-body-enhanced">
              <div class="project-summary-card">
                <div class="summary-header">
                  <el-icon :size="32" color="#409EFF"><FolderOpened /></el-icon>
                  <div class="summary-info">
                    <h4 class="summary-title">{{ selectedProjectInfo.name }}</h4>
                    <span class="summary-id">ID: {{ selectedProjectInfo.id }}</span>
                  </div>
                </div>
                
                <div class="summary-stats">
                  <div class="summary-stat-item">
                    <div class="stat-icon-wrapper stat-blue">
                      <el-icon><Files /></el-icon>
                    </div>
                    <div class="stat-detail">
                      <div class="stat-number">{{ files.length }}</div>
                      <div class="stat-text">资源文件</div>
                    </div>
                  </div>
                  <div class="summary-stat-divider"></div>
                  <div class="summary-stat-item">
                    <div class="stat-icon-wrapper stat-green">
                      <el-icon><Document /></el-icon>
                    </div>
                    <div class="stat-detail">
                      <div class="stat-number">{{ getResourceTypeCount('requirement') }}</div>
                      <div class="stat-text">需求文档</div>
                    </div>
                  </div>
                </div>

                <div class="resource-preview-list">
                  <div class="preview-list-title">资源类型分布</div>
                  <div class="preview-type-items">
                    <div class="type-item">
                      <div class="type-bar type-requirement" :style="{ width: getResourceTypePercentage('requirement') + '%' }"></div>
                      <span class="type-label">需求文档</span>
                      <span class="type-count">{{ getResourceTypeCount('requirement') }}</span>
                    </div>
                    <div class="type-item">
                      <div class="type-bar type-ui" :style="{ width: getResourceTypePercentage('ui_mockup') + '%' }"></div>
                      <span class="type-label">UI原型</span>
                      <span class="type-count">{{ getResourceTypeCount('ui_mockup') }}</span>
                    </div>
                    <div class="type-item">
                      <div class="type-bar type-api" :style="{ width: getResourceTypePercentage('api_doc') + '%' }"></div>
                      <span class="type-label">API文档</span>
                      <span class="type-count">{{ getResourceTypeCount('api_doc') }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="next-action-card">
                <div class="action-hint">
                  <el-icon><ArrowRight /></el-icon>
                  <span>准备就绪，可以继续下一步</span>
                </div>
                <el-button type="primary" class="next-btn-large" @click="goToNextStep">
                  下一步：选择需求
                  <el-icon><ArrowRight /></el-icon>
                </el-button>
              </div>
            </div>
          </div>

          <!-- 步骤2右侧：资源详情预览 -->
          <div v-else-if="currentStep === 1 && selectedResource" key="preview2" class="preview-card">
            <div class="preview-header">
              <el-icon><View /></el-icon>
              <span>资源详情</span>
            </div>
            <div class="preview-body">
              <div class="resource-detail-card">
                <div class="detail-icon">
                  <el-icon :size="48" color="#409EFF">
                    <component :is="getResourceIcon(selectedResource.resource_type)" />
                  </el-icon>
                </div>
                <div class="detail-info">
                  <div class="detail-name">{{ selectedResource.display_name }}</div>
                  <div class="detail-meta">
                    <el-tag :type="getResourceTypeTagType(selectedResource.resource_type)" size="small">
                      {{ getResourceTypeLabel(selectedResource.resource_type) }}
                    </el-tag>
                  </div>
                  <div class="detail-stats">
                    <div class="stat-item">
                      <span class="stat-label">大小</span>
                      <span class="stat-value">{{ selectedResource.size_text }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">时间</span>
                      <span class="stat-value">{{ selectedResource.time_text }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="next-step-hint">
                <el-button type="primary" @click="goToNextStep">
                  下一步：AI提取
                  <el-icon><ArrowRight /></el-icon>
                </el-button>
              </div>
            </div>
          </div>

          <!-- 步骤2右侧：未选择资源提示 -->
          <div v-else-if="currentStep === 1 && !selectedResource" key="preview2-empty" class="preview-card preview-empty">
            <el-empty description="请从左侧选择一个需求资源" :image-size="100" />
          </div>

          <!-- 步骤3右侧：提取统计 -->
          <div v-else-if="currentStep === 2" key="preview3" class="preview-card">
            <div class="preview-header">
              <el-icon><DataAnalysis /></el-icon>
              <span>{{ extracting ? '提取中...' : testPoints.length > 0 ? '提取结果' : '等待提取' }}</span>
            </div>
            <div class="preview-body">
              <div v-if="extracting" class="stats-skeleton">
                <el-skeleton :rows="4" animated />
              </div>
              <div v-else-if="testPoints.length > 0" class="extract-stats">
                <div class="stat-card total">
                  <div class="stat-number">{{ testPoints.length }}</div>
                  <div class="stat-label">测试点总数</div>
                </div>
                <div class="priority-distribution">
                  <div class="distribution-title">优先级分布</div>
                  <div class="distribution-items">
                    <div class="dist-item high">
                      <span class="dist-count">{{ getPriorityCount(1) }}</span>
                      <span class="dist-label">高优先级</span>
                    </div>
                    <div class="dist-item medium">
                      <span class="dist-count">{{ getPriorityCount(2) }}</span>
                      <span class="dist-label">中优先级</span>
                    </div>
                    <div class="dist-item low">
                      <span class="dist-count">{{ getPriorityCount(3) }}</span>
                      <span class="dist-label">低优先级</span>
                    </div>
                  </div>
                </div>
                <div class="module-distribution">
                  <div class="distribution-title">模块分布</div>
                  <div class="module-list">
                    <div v-for="(count, module) in getModuleDistribution()" :key="module" class="module-item">
                      <span class="module-name">{{ module }}</span>
                      <span class="module-count">{{ count }}</span>
                    </div>
                  </div>
                </div>
                <div class="next-step-hint">
                  <el-button type="primary" @click="goToNextStep">
                    下一步：管理测试点
                    <el-icon><ArrowRight /></el-icon>
                  </el-button>
                </div>
              </div>
              <div v-else class="waiting-state">
                <el-empty description="等待提取测试点" :image-size="100" />
              </div>
            </div>
          </div>

          <!-- 步骤4右侧：操作指南 -->
          <div v-else-if="currentStep === 3" key="preview4" class="preview-card">
            <div class="preview-header">
              <el-icon><Guide /></el-icon>
              <span>操作指南</span>
            </div>
            <div class="preview-body">
              <div class="guide-list">
                <div class="guide-item">
                  <el-icon color="#67C23A"><Check /></el-icon>
                  <span>支持批量选择和删除测试点</span>
                </div>
                <div class="guide-item">
                  <el-icon color="#409EFF"><Edit /></el-icon>
                  <span>可编辑单个测试点的详细信息</span>
                </div>
                <div class="guide-item">
                  <el-icon color="#E6A23C"><FolderAdd /></el-icon>
                  <span>保存到数据库以便后续使用</span>
                </div>
                <div class="guide-item">
                  <el-icon color="#F56C6C"><MagicStick /></el-icon>
                  <span>一键生成完整测试用例</span>
                </div>
              </div>
              <div class="quick-stats" v-if="testPoints.length > 0">
                <div class="quick-stat-item">
                  <span class="qs-label">总测试点</span>
                  <span class="qs-value">{{ savedFromDb ? dbTotal : testPoints.length }}</span>
                </div>
                <div class="quick-stat-item">
                  <span class="qs-label">已选中</span>
                  <span class="qs-value highlight">{{ selectedRows.length }}</span>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </div>

    <!-- 编辑测试点对话框 -->
    <el-dialog
      v-model="dialogVisible"
      title="编辑测试点"
      width="600px"
      destroy-on-close
    >
      <el-form :model="editForm" label-width="120px">
        <el-form-item label="模块" required>
          <el-input v-model="editForm.module" placeholder="如：登录模块" />
        </el-form-item>
        <el-form-item label="功能" required>
          <el-input v-model="editForm.function" placeholder="如：账号密码登录" />
        </el-form-item>
        <el-form-item label="测试点描述" required>
          <el-input
            v-model="editForm.point"
            type="textarea"
            :rows="4"
            placeholder="请输入测试点描述"
          />
        </el-form-item>
        <el-form-item label="优先级" required>
          <el-select v-model="editForm.priority" placeholder="请选择优先级">
            <el-option :value="1" label="高" />
            <el-option :value="2" label="中" />
            <el-option :value="3" label="低" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveTestPoint">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  ArrowLeft,
  ArrowRight,
  MagicStick,
  Close,
  Check,
  Refresh,
  Edit,
  Delete,
  FolderOpened,
  Document,
  List,
  InfoFilled,
  View,
  DataAnalysis,
  Guide,
  FolderAdd,
  Search,
  Files,
  Picture,
  DocumentCopy,
  RefreshLeft,
  CircleCheckFilled
} from '@element-plus/icons-vue';
import request from '@/utils/request';
import { testPointApi } from '@/api/testPoint';

// ==================== 类型定义 ====================

interface TestPoint {
  id: number;
  module: string;
  function: string;
  point: string;
  priority: number;
  ai_prompt?: string;
  create_time?: string;
  _raw?: any;
}

interface Project {
  id: number;
  name: string;
}

interface File {
  id: number;
  project_id: number;
  file_name: string;
  file_url: string;
  file_type: string;
  size: number;
  upload_time: string;
  file_source: string;
  resource_type?: string;
}

interface ResourceRow {
  source: 'file';
  id: number;
  project_id: number;
  display_name: string;
  resource_type: string;
  type_label: string;
  size_text: string;
  time_text: string;
}

interface TestPointListResponse {
  code: number;
  data?: {
    items: TestPoint[];
    total: number;
  };
  message?: string;
}

// ==================== 路由 ====================

const router = useRouter();
const route = useRoute();

// ==================== 步骤控制 ====================

const currentStep = ref(0);

// ==================== 表单与状态 ====================

const formData = reactive({
  project_id: '' as number | ''
});

const projects = ref<Project[]>([]);
const files = ref<File[]>([]);
const selectedResource = ref<ResourceRow | null>(null);
const testPoints = ref<TestPoint[]>([]);
const extracting = ref(false);
const saving = ref(false);
const batchDeleting = ref(false);
const deleting = ref(false);
const savedFromDb = ref(false);
const loadingTestPoints = ref(false);

// 多选相关
const selectedRows = ref<any[]>([]);
const testPointTable = ref();
const currentPage = ref(1);
const pageSize = ref(10);
const dbTotal = ref(0);

// 进度相关
const progress = ref(0);
const progressText = ref('准备提取...');
const progressInterval = ref<ReturnType<typeof setInterval> | null>(null);

// 错误与对话框
const errorMessage = ref('');
const dialogVisible = ref(false);
const resourceTypeFilter = ref('');

// 编辑表单
const editForm = reactive<TestPoint>({
  id: 0,
  module: '',
  function: '',
  point: '',
  priority: 2
});

const editingIndex = ref(-1);
const updating = ref(false);

// ==================== 计算属性 ====================

// 已选项目信息
const selectedProjectInfo = computed(() => {
  if (!formData.project_id) return null;
  return projects.value.find(p => p.id === formData.project_id) || null;
});

// 资源行数据
const resourceRows = computed<ResourceRow[]>(() => {
  return files.value.map((f) => ({
    source: 'file',
    id: f.id,
    project_id: f.project_id,
    display_name: f.file_name,
    resource_type: f.resource_type || 'other',
    type_label: getResourceTypeLabel(f.resource_type || 'other'),
    size_text: formatFileSize(f.size),
    time_text: f.upload_time
  }));
});

// 过滤后的资源列表
const filteredResourceRows = computed(() => {
  if (!resourceTypeFilter.value) return resourceRows.value;
  return resourceRows.value.filter(r => r.resource_type === resourceTypeFilter.value);
});

// 进度状态
const progressStatus = computed(() => {
  if (progress.value === 100) return 'success';
  if (errorMessage.value) return 'exception';
  return '';
});

// 分页后的测试点
const paginatedTestPoints = computed(() => {
  if (savedFromDb.value) return testPoints.value;
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return testPoints.value.slice(start, end);
});

// ==================== API调用方法 ====================

// 获取项目列表
const getProjects = async () => {
  try {
    const response = await request.get('/api/v1/project/list');
    if (response && response.data && response.data.items) {
      projects.value = response.data.items.filter((project: Project) => project.name !== '默认项目');
    } else {
      projects.value = [];
    }
  } catch (error) {
    console.error('获取项目列表失败:', error);
    projects.value = [];
  }
};

// 加载上传文件
const loadResources = async (projectId: number) => {
  try {
    const fileRes = await request.get(`/api/v1/file/list/${projectId}`);
    if (fileRes && fileRes.data && fileRes.data.items) {
      files.value = fileRes.data.items;
    } else {
      files.value = [];
    }
  } catch (error) {
    console.error('获取文件列表失败:', error);
    files.value = [];
  }
};

// 加载已保存的测试点
const loadSavedTestPoints = async (projectId: number, page = 1) => {
  loadingTestPoints.value = true;
  try {
    const response: TestPointListResponse = await request.get(`/api/v1/test-point/list/${projectId}`, {
      params: { page, page_size: pageSize.value }
    });
    if (response?.code === 200 && response.data) {
      testPoints.value = (response.data.items || []) as TestPoint[];
      dbTotal.value = response.data.total || 0;
      savedFromDb.value = true;
      currentPage.value = page;
      console.log(`从数据库加载了 ${testPoints.value.length} 个测试点，共 ${dbTotal.value} 个`);
    } else {
      console.error('加载测试点失败，响应异常:', response);
    }
  } catch (error: any) {
    console.error('加载测试点失败:', error);
  } finally {
    loadingTestPoints.value = false;
  }
};

// ==================== 事件处理 ====================

// 处理项目变更
const handleProjectChange = async (projectId: number) => {
  if (projectId) {
    await loadResources(projectId);
    selectedResource.value = null;
    testPoints.value = [];
    savedFromDb.value = false;
    dbTotal.value = 0;
    currentPage.value = 1;
    errorMessage.value = '';
    await loadSavedTestPoints(projectId);
  } else {
    files.value = [];
    selectedResource.value = null;
    testPoints.value = [];
    savedFromDb.value = false;
    dbTotal.value = 0;
    currentPage.value = 1;
  }
};

// 选择资源行
const handleResourceSelect = (row: ResourceRow) => {
  selectedResource.value = row;
};

// 跳转到提取步骤
const goToExtract = (row?: ResourceRow) => {
  const target = row ?? selectedResource.value;
  if (!target) {
    ElMessage.warning('请先选择需求文件');
    return;
  }
  selectedResource.value = target;
  currentStep.value = 2;
};

// 开始提取
const startExtract = () => {
  if (!selectedResource.value) {
    ElMessage.warning('请先选择需求文件');
    return;
  }
  extractTestPoints();
};

// 重试提取
const retryExtract = () => {
  errorMessage.value = '';
  extractTestPoints();
};

// 步骤导航
const goToNextStep = () => {
  // 前置校验：确保当前步骤的必要操作已完成
  if (currentStep.value === 0 && !formData.project_id) {
    ElMessage.warning('请先选择项目');
    return;
  }
  if (currentStep.value === 1 && !selectedResource.value) {
    ElMessage.warning('请先选择需求资源');
    return;
  }
  if (currentStep.value < 3) {
    currentStep.value++;
  }
};

const goToPrevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--;
  }
};

// 分页处理
const handlePageChange = (page: number) => {
  if (savedFromDb.value && formData.project_id) {
    loadSavedTestPoints(Number(formData.project_id), page);
  } else {
    currentPage.value = page;
  }
};

// ==================== 核心业务逻辑 ====================

// 提取测试点
const extractTestPoints = async () => {
  const target = selectedResource.value;
  if (!target) {
    ElMessage.warning('请先选择需求文件');
    return;
  }

  // 防重复点击：如果正在提取中则忽略
  if (extracting.value) {
    ElMessage.warning('正在提取中，请稍候');
    return;
  }

  // 清空之前的状态
  testPoints.value = [];
  savedFromDb.value = false;
  dbTotal.value = 0;
  currentPage.value = 1;
  errorMessage.value = '';
  extracting.value = true;
  progress.value = 0;
  progressText.value = '正在读取文件内容...';

  // 清理可能残留的定时器
  if (progressInterval.value) {
    clearInterval(progressInterval.value);
    progressInterval.value = null;
  }

  const PHASES = [
    { end: 20, text: '正在读取文件内容...' },
    { end: 40, text: '正在解析文档结构...' },
    { end: 65, text: 'AI 正在分析需求并提取测试点...' },
    { end: 85, text: '正在整理测试点数据...' },
  ];
  let phaseIndex = 0;

  progressInterval.value = setInterval(() => {
    if (phaseIndex < PHASES.length) {
      const targetProgress = PHASES[phaseIndex].end;
      if (progress.value < targetProgress) {
        progress.value = Math.round(Math.min(progress.value + Math.random() * 4 + 1, targetProgress));
        progressText.value = PHASES[phaseIndex].text;
      } else {
        phaseIndex++;
      }
    }
  }, 300);

  try {
    progressText.value = PHASES[PHASES.length - 1].text;

    const response = await request.post('/api/v1/test-point/extract', {
      file_id: target.id
    });

    if (response && response.data && response.data.items) {
      testPoints.value = response.data.items.map((item: any, index: number) => ({
        id: item.id || index + 1,
        module: item.module || '',
        function: item.function || '',
        point: item.point || '',
        priority: item.priority || 2,
        ai_prompt: item.ai_prompt,
        create_time: item.create_time,
        _raw: item
      }));
      savedFromDb.value = false;
      ElMessage.success(`测试点提取成功，共 ${testPoints.value.length} 个`);
    } else {
      ElMessage.warning('未提取到测试点');
    }

    clearInterval(progressInterval.value);
    progressInterval.value = null;
    progress.value = 100;
    progressText.value = `提取完成！共 ${testPoints.value.length} 个测试点`;
  } catch (error: any) {
    if (progressInterval.value) {
      clearInterval(progressInterval.value);
      progressInterval.value = null;
    }
    // 失败时不显示100%，保持当前进度或重置为0
    progress.value = 0;
    // 错误信息脱敏：不直接暴露后端内部细节
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && !detail.includes('traceback') && !detail.includes('stack')) {
      errorMessage.value = detail.length > 200 ? detail.slice(0, 200) + '...' : detail;
    } else if (error.response?.data?.message) {
      errorMessage.value = error.response.data.message;
    } else {
      errorMessage.value = '测试点提取失败，请检查网络连接或稍后重试';
    }

    ElMessage.error('提取失败，请查看错误信息');
  } finally {
    extracting.value = false;
  }
};

// 取消提取
const handleCancel = () => {
  ElMessageBox.confirm('确定要取消提取吗？', '取消确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    // 清理定时器防止内存泄漏
    if (progressInterval.value) {
      clearInterval(progressInterval.value);
      progressInterval.value = null;
    }
    extracting.value = false;
    progress.value = 0;
    progressText.value = '已取消';
    ElMessage.info('提取已取消');
  });
};

// ==================== 多选和批量操作 ====================

const handleSelectionChange = (rows: any[]) => {
  selectedRows.value = rows;
};

const clearSelection = () => {
  selectedRows.value = [];
  if (testPointTable.value) {
    testPointTable.value.clearSelection();
  }
};

const batchDeleteTestPoints = async () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的测试点');
    return;
  }

  if (!formData.project_id) {
    ElMessage.warning('请先选择项目');
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 个测试点吗？此操作不可恢复！`,
      '批量删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    batchDeleting.value = true;

    const ids = selectedRows.value.map(row => row.id);

    const result = await testPointApi.batchDelete(
      Number(formData.project_id),
      ids
    );

    if (result.code === 200) {
      ElMessage.success(result.message || `成功删除 ${result.data.deleted_count} 个测试点`);

      clearSelection();

      if (savedFromDb.value) {
        await loadSavedTestPoints(Number(formData.project_id), currentPage.value);
      } else {
        const deletedIds = new Set(ids);
        testPoints.value = testPoints.value.filter(item => !deletedIds.has(item.id));
      }
    } else {
      throw new Error(result.message || '批量删除失败');
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error);
      ElMessage.error(error?.response?.data?.detail || error?.message || '批量删除失败，请稍后重试');
    }
  } finally {
    batchDeleting.value = false;
  }
};

// ==================== 编辑功能 ====================

const editTestPoint = (testPoint: TestPoint) => {
  const index = testPoints.value.findIndex(item => item.id === testPoint.id);
  editingIndex.value = index;
  editForm.id = testPoint.id;
  editForm.module = testPoint.module;
  editForm.function = testPoint.function || '';
  editForm.point = testPoint.point;
  editForm.priority = testPoint.priority || 2;
  dialogVisible.value = true;
};

const saveTestPoint = async () => {
  if (!editForm.module || !editForm.point) {
    ElMessage.warning('请填写完整的测试点信息');
    return;
  }

  try {
    updating.value = true;

    const index = editingIndex.value;
    if (index !== -1 && index < testPoints.value.length) {
      const currentPoint = testPoints.value[index];

      if (currentPoint.id && savedFromDb.value && formData.project_id) {
        const result = await testPointApi.update(currentPoint.id, {
          project_id: Number(formData.project_id),
          module: editForm.module,
          function: editForm.function || '',
          point: editForm.point,
          priority: editForm.priority,
          ai_prompt: currentPoint.ai_prompt
        });

        if (result.code === 200) {
          testPoints.value[index] = {
            ...result.data,
            ai_prompt: result.data.ai_prompt ?? undefined,
            _raw: result.data
          };
          ElMessage.success('测试点更新成功');
          dialogVisible.value = false;

          await loadSavedTestPoints(Number(formData.project_id), currentPage.value);
        } else {
          throw new Error(result.message || '更新失败');
        }
      } else {
        testPoints.value[index] = { ...editForm };
        ElMessage.success('测试点更新成功（本地）');
        dialogVisible.value = false;
      }
    }
  } catch (error: any) {
    console.error('保存测试点失败:', error);
    ElMessage.error(error?.response?.data?.detail || error?.message || '保存失败，请稍后重试');
  } finally {
    updating.value = false;
  }
};

// ==================== 删除功能 ====================

const deleteTestPoint = async (testPoint: TestPoint) => {
  try {
    if (!formData.project_id) {
      ElMessage.warning('请先选择项目');
      return;
    }

    deleting.value = true;

    if (testPoint.id && savedFromDb.value) {
      const result = await testPointApi.delete(
        testPoint.id,
        Number(formData.project_id)
      );

      if (result.code === 200) {
        ElMessage.success('删除成功');
        let targetPage = currentPage.value;
        const totalAfterDelete = dbTotal.value - 1;
        const maxPage = Math.max(1, Math.ceil(totalAfterDelete / pageSize.value));
        if (targetPage > maxPage) {
          targetPage = maxPage;
        }
        await loadSavedTestPoints(Number(formData.project_id), targetPage);
      } else {
        ElMessage.error(result.message || '删除失败');
      }
    } else {
      const index = testPoints.value.findIndex(item => item.id === testPoint.id);
      if (index !== -1) {
        testPoints.value.splice(index, 1);
      }
      ElMessage.success('删除成功（本地）');
    }
  } catch (error: any) {
    console.error('删除测试点失败:', error);
    ElMessage.error(error?.response?.data?.detail || error?.message || '删除失败，请稍后重试');
  } finally {
    deleting.value = false;
  }
};

// ==================== 保存与生成 ====================

const saveToDatabase = async () => {
  if (testPoints.value.length === 0) {
    ElMessage.warning('没有可保存的测试点');
    return;
  }

  const projectId = selectedResource.value?.project_id || (formData.project_id ? Number(formData.project_id) : 0);
  if (!projectId) {
    ElMessage.warning('请先选择项目');
    return;
  }

  saving.value = true;
  try {
    const rawData = testPoints.value
      .map(tp => tp._raw || {
        module: tp.module,
        function: tp.function,
        point: tp.point,
        priority: tp.priority
      })
      .filter(raw => raw && raw.module && raw.point);

    if (rawData.length === 0) {
      ElMessage.warning('没有有效的测试点数据');
      saving.value = false;
      return;
    }

    const response: any = await request.post(
      '/api/v1/test-point/batch-save',
      rawData,
      {
        params: { project_id: projectId },
        headers: { 'Content-Type': 'application/json' }
      }
    );

    if (response?.code === 200) {
      ElMessage.success(response?.message || `成功保存 ${rawData.length} 个测试点`);
      savedFromDb.value = true;
      await loadSavedTestPoints(projectId);
    } else {
      ElMessage.error(response?.msg || response?.message || '保存失败');
    }
  } catch (error: any) {
    console.error('保存测试点失败:', error);
    ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '保存到数据库失败');
  } finally {
    saving.value = false;
  }
};

const generateTestCases = () => {
  if (testPoints.value.length === 0) {
    ElMessage.warning('请先提取或加载测试点');
    return;
  }

  const projectId = selectedResource.value?.project_id || (formData.project_id ? Number(formData.project_id) : 0);
  if (!projectId) {
    ElMessage.warning('请先选择项目');
    return;
  }

  const query: Record<string, string> = {
    project_id: String(projectId),
    test_point_ids: JSON.stringify(testPoints.value.map(tp => tp.id))
  };

  if (selectedResource.value) {
    query.file_id = String(selectedResource.value.id);
    query.filename = selectedResource.value.display_name;
  }

  router.push({ path: '/home/case/ai-generate', query });
};

// ==================== 辅助方法 ====================

const handleBack = () => {
  router.push('/home/case');
};

const formatFileSize = (size: number): string => {
  if (size < 1024) {
    return size + ' B';
  } else if (size < 1024 * 1024) {
    return (size / 1024).toFixed(2) + ' KB';
  } else {
    return (size / (1024 * 1024)).toFixed(2) + ' MB';
  }
};

const getResourceTypeLabel = (type: string) => {
  const labelMap: Record<string, string> = {
    requirement: '需求文档',
    ui_mockup: 'UI原型图',
    api_doc: 'API文档',
    test_data: '测试数据',
    other: '其他'
  };
  return labelMap[type] || type;
};

const getResourceTypeTagType = (type: string) => {
  const tagMap: Record<string, string> = {
    requirement: 'primary',
    ui_mockup: 'warning',
    api_doc: 'success',
    test_data: 'info',
    other: 'info'
  };
  return tagMap[type] || 'info';
};

const getResourceIcon = (type: string) => {
  const iconMap: Record<string, string> = {
    requirement: 'Document',
    ui_mockup: 'Picture',
    api_doc: 'DocumentCopy',
    test_data: 'Files',
    other: 'Document'
  };
  return iconMap[type] || 'Document';
};

const getPriorityTagType = (priority: number | string) => {
  const p = Number(priority);
  if (p === 1) return 'danger';
  if (p === 2) return 'warning';
  return 'info';
};

const getPriorityLabel = (priority: number | string) => {
  const p = Number(priority);
  if (p === 1) return '高';
  if (p === 2) return '中';
  return '低';
};

const getPriorityCount = (priority: number): number => {
  return testPoints.value.filter(tp => tp.priority === priority).length;
};

const getModuleDistribution = (): Record<string, number> => {
  const distribution: Record<string, number> = {};
  testPoints.value.forEach(tp => {
    const module = tp.module || '未分类';
    distribution[module] = (distribution[module] || 0) + 1;
  });
  return distribution;
};

const getResourceTypeCount = (type: string): number => {
  return files.value.filter(f => f.resource_type === type).length;
};

const getResourceTypePercentage = (type: string): number => {
  const total = files.value.length;
  if (total === 0) return 0;
  return Math.round((getResourceTypeCount(type) / total) * 100);
};

const moduleCount = computed(() => {
  const modules = new Set(testPoints.value.map(tp => tp.module || '未分类'));
  return modules.size;
});

// ==================== 初始化 ====================

onMounted(async () => {
  await getProjects();

  const idParam = Number(route.query.file_id);
  const projectIdParam = Number(route.query.project_id);

  if (projectIdParam) {
    formData.project_id = projectIdParam;
    await loadResources(projectIdParam);
    await loadSavedTestPoints(projectIdParam);
    if (idParam) {
      const row = resourceRows.value.find((r) => r.id === idParam);
      if (row) {
        selectedResource.value = row;
      }
    }
  }
});

onUnmounted(() => {
  if (progressInterval.value) {
    clearInterval(progressInterval.value);
    progressInterval.value = null;
  }
});
</script>

<style>
/* ==================== 全局设计令牌（非scoped，确保:root生效） ==================== */
.test-point-extract-container {
  --primary-color: #409EFF;
  --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --border-radius: 12px;
  --border-radius-sm: 8px;
  --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.08);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);
  --shadow-xl: 0 12px 48px rgba(0, 0, 0, 0.15);
  --spacing-xs: 8px;
  --spacing-sm: 12px;
  --spacing-md: 16px;
  --spacing-lg: 20px;
  --spacing-xl: 24px;
  --spacing-xxl: 32px;
}
</style>

<style scoped>
/* ==================== 容器布局 - 渐变背景 ==================== */
.test-point-extract-container {
  padding: var(--spacing-xl);
  max-width: 1400px;
  margin: 0 auto;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  min-height: calc(100vh - 120px);
  border-radius: var(--border-radius);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xl);
  padding: var(--spacing-lg);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-sm);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
}

.header-left h2 {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #303133;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.page-header .el-button {
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.page-header .el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.step-nav-buttons {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
}

.step-nav-buttons .el-button {
  font-weight: 600;
}

/* ==================== 步骤条增强 ==================== */
.steps-wrapper {
  margin-bottom: var(--spacing-xl);
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  padding: var(--spacing-xl) var(--spacing-xxl);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-md);
  position: relative;
  overflow: hidden;
}

.steps-wrapper::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
}

.steps-enhanced :deep(.el-steps) {
  margin-top: 8px;
}

.step-icon-custom {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-size: 18px;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
}

/* ==================== 主内容区（左右分栏） ==================== */
.main-content {
  display: flex;
  gap: var(--spacing-xl);
  min-height: 600px;
}

.left-panel {
  flex: 1;
  min-width: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  position: relative;
}

.left-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, #409EFF 0%, #67C23A 100%);
}

.right-panel {
  width: 400px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  position: relative;
}

.right-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, #F56C6C 0%, #E6A23C 50%, #409EFF 100%);
}

.right-panel-enhanced {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%);
}

/* ==================== 步骤内容增强 ==================== */
.step-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.step-content.step-full {
  min-height: 650px;
}

.step-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid #EBEEF5;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  background: #FAFAFA;
  position: relative;
}

.step-title-gradient {
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-bottom: 2px solid #E4E7ED;
}

.step-title .el-icon {
  color: var(--primary-color);
  font-size: 22px;
}

.step-badge {
  margin-left: auto;
  padding: 4px 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.step-body {
  flex: 1;
  padding: var(--spacing-xl);
  overflow-y: auto;
  background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
}

.step-body-enhanced {
  padding: var(--spacing-xxl);
}

/* ==================== 项目选择引导界面 ==================== */
.project-selection-guide {
  text-align: center;
}

.guide-illustration {
  position: relative;
  margin-bottom: var(--spacing-xl);
  display: inline-block;
}

.illustration-circle {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
  animation: float 3s ease-in-out infinite;
  position: relative;
  z-index: 2;
  will-change: transform;
}

@keyframes float {
  0%, 100% { transform: translateY(0px) translateZ(0); }
  50% { transform: translateY(-10px) translateZ(0); }
}

.floating-icons {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.float-icon {
  position: absolute;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: white;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-md);
  animation: floatIcon 4s ease-in-out infinite;
  z-index: 3;
  will-change: transform;
}

.float-icon.float-1 {
  top: 10px;
  right: -10px;
  color: #409EFF;
  animation-delay: 0s;
}

.float-icon.float-2 {
  bottom: 15px;
  left: -15px;
  color: #67C23A;
  animation-delay: 1s;
}

.float-icon.float-3 {
  bottom: -5px;
  right: 20px;
  color: #E6A23C;
  animation-delay: 2s;
}

@keyframes floatIcon {
  0%, 100% { transform: translateY(0) translateZ(0) rotate(0deg); }
  33% { transform: translateY(-8px) translateZ(0) rotate(5deg); }
  66% { transform: translateY(4px) translateZ(0) rotate(-3deg); }
}

.guide-content {
  margin-bottom: var(--spacing-xl);
}

.guide-title {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 var(--spacing-sm) 0;
}

.guide-description {
  font-size: 16px;
  color: #606266;
  line-height: 1.6;
  margin: 0;
}

.project-select-enhanced {
  margin-bottom: var(--spacing-xl);
}

.project-select-enhanced :deep(.el-select) {
  border-radius: var(--border-radius);
}

.project-select-enhanced :deep(.el-input__wrapper) {
  border-radius: var(--border-radius);
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
  transition: all 0.3s ease;
}

.project-select-enhanced :deep(.el-input__wrapper:hover) {
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.25);
}

.project-option {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 4px 0;
}

.workflow-hint {
  margin-top: var(--spacing-xl);
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: var(--border-radius-sm);
  border: 1px solid #E4E7ED;
}

.workflow-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
}

.wf-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.wf-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.wf-step span {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
}

.wf-arrow {
  color: #C0C4CC;
  font-size: 16px;
}

/* ==================== 项目已选视图 ==================== */
.project-selected-view {
  width: 100%;
}

.selected-project-card {
  background: white;
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-md);
  overflow: hidden;
  border: 1px solid #E4E7ED;
}

.project-card-header {
  padding: var(--spacing-xl);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  color: white;
}

.project-icon-large {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.project-info-main {
  flex: 1;
}

.project-name-large {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 24px;
  font-weight: 700;
  color: white;
}

.project-meta-tags {
  display: flex;
  gap: var(--spacing-sm);
}

.project-meta-tags .el-tag {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
  color: white;
}

.project-card-body {
  padding: var(--spacing-xl);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
}

.grid-item {
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius-sm);
  text-align: center;
  border: 1px solid #EBEEF5;
  transition: all 0.3s ease;
}

.grid-item:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: #409EFF;
}

.grid-icon {
  margin-bottom: var(--spacing-sm);
}

.grid-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 4px;
}

.grid-label {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}

.project-card-footer {
  padding: var(--spacing-lg) var(--spacing-xl);
  background: #FAFAFA;
  border-top: 1px solid #EBEEF5;
  display: flex;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.project-card-footer .el-button {
  flex: 1;
  border-radius: 8px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.project-card-footer .el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

/* ==================== 筛选栏 ==================== */
.filter-bar {
  margin-bottom: var(--spacing-md);
}

/* ==================== 资源列表 ==================== */
.resource-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.resource-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  border: 2px solid #EBEEF5;
  border-radius: var(--border-radius);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: white;
  position: relative;
  overflow: hidden;
}

.resource-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: transparent;
  transition: all 0.3s ease;
}

.resource-item:hover {
  border-color: var(--primary-color);
  box-shadow: var(--shadow-lg);
  transform: translateX(4px);
}

.resource-item:hover::before {
  background: var(--primary-color);
}

.resource-item.active {
  border-color: var(--primary-color);
  background: linear-gradient(135deg, #ECF5FF 0%, #D9ECFF 100%);
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.2);
}

.resource-item.active::before {
  background: var(--primary-color);
}

.resource-icon {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: var(--border-radius-sm);
  color: #606266;
  transition: all 0.3s ease;
}

.resource-item:hover .resource-icon,
.resource-item.active .resource-icon {
  background: linear-gradient(135deg, #409EFF 0%, #66b1ff 100%);
  color: white;
  transform: scale(1.05);
}

.resource-info {
  flex: 1;
  min-width: 0;
}

.resource-name {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  font-size: 13px;
  color: #909399;
}

.resource-size,
.resource-time {
  font-size: 12px;
}

.resource-action {
  flex-shrink: 0;
}

.resource-action .el-button {
  border-radius: 8px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.resource-action .el-button:hover {
  transform: scale(1.05);
  box-shadow: var(--shadow-md);
}

/* ==================== 已选资源卡片 ==================== */
.selected-resource-card {
  background: linear-gradient(135deg, #ECF5FF 0%, #D9ECFF 100%);
  border-radius: var(--border-radius);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
  border: 2px solid #B3D8FF;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
}

.resource-summary {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
}

.resource-summary .el-icon {
  color: var(--primary-color);
}

.resource-summary .resource-name {
  font-weight: 700;
  font-size: 17px;
  color: #303133;
}

.resource-summary .resource-meta {
  font-size: 14px;
  color: #606266;
  margin-top: 6px;
}

/* ==================== 提取进度 ==================== */
.extract-progress {
  text-align: center;
}

.skeleton-wrapper {
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius);
  border: 1px solid #EBEEF5;
}

.progress-section {
  padding: var(--spacing-lg) 0;
}

.progress-section :deep(.el-progress-bar__outer) {
  border-radius: 20px;
}

.progress-section :deep(.el-progress-bar__inner) {
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 20px;
}

.progress-text-animated {
  margin: var(--spacing-lg) 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--primary-color);
  animation: pulse 2s ease-in-out infinite;
  will-change: opacity;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* ==================== 提取错误 ==================== */
.extract-error {
  padding: var(--spacing-lg) 0;
}

/* ==================== 准备提取状态 ==================== */
.extract-ready {
  padding: var(--spacing-xxl) 0;
}

.ready-icon {
  margin-bottom: var(--spacing-lg);
}

.ready-text {
  color: #606266;
  font-size: 15px;
  margin-bottom: var(--spacing-xl);
  line-height: 1.6;
}

/* ==================== 提取成功状态 ==================== */
.extract-success {
  padding: var(--spacing-lg) 0;
  text-align: center;
}

.success-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #f0f9eb 0%, #ecf5ff 100%);
  border-radius: var(--border-radius);
  border: 1px solid #e1f3d8;
}

.success-icon-wrapper {
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #67C23A 0%, #85ce61 100%);
  border-radius: 50%;
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.3);
}

.success-info {
  text-align: left;
}

.success-title {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}

.success-desc {
  margin: 0;
  font-size: 15px;
  color: #606266;
}

.success-desc strong {
  color: #67C23A;
  font-size: 18px;
}

.success-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-xl);
}

.stat-item {
  padding: var(--spacing-md);
  border-radius: var(--border-radius-sm);
  text-align: center;
  transition: transform 0.2s ease;
}

.stat-item:hover {
  transform: translateY(-2px);
}

.stat-number {
  display: block;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  display: block;
  font-size: 13px;
  color: #909399;
  margin-top: var(--spacing-xs);
}

.stat-high { background: #fef0f0; border: 1px solid #fde2e2; }
.stat-high .stat-number { color: #F56C6C; }

.stat-medium { background: #fdf6ec; border: 1px solid #faecd8; }
.stat-medium .stat-number { color: #E6A23C; }

.stat-low { background: #f0f9eb; border: 1px solid #e1f3d8; }
.stat-low .stat-number { color: #67C23A; }

.stat-modules { background: #ecf5ff; border: 1px solid #d9ecff; }
.stat-modules .stat-number { color: #409EFF; }

.success-actions {
  display: flex;
  justify-content: center;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.success-actions .el-button {
  font-weight: 600;
  border-radius: 10px;
  padding: 12px 28px;
  font-size: 15px;
  transition: all 0.3s ease;
}

.success-actions .el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

@media (max-width: 768px) {
  .success-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .success-header {
    flex-direction: column;
    text-align: center;
  }
  .success-info {
    text-align: center;
  }
}

/* ==================== 批量工具栏 ==================== */
.batch-toolbar {
  margin-bottom: var(--spacing-lg);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius);
  border: 1px solid #E4E7ED;
  box-shadow: var(--shadow-sm);
}

.batch-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.action-buttons {
  display: flex;
  gap: var(--spacing-sm);
}

.action-buttons .el-button {
  border-radius: 8px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.action-buttons .el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

/* ==================== 表格 ==================== */
.table-wrapper {
  overflow-x: auto;
  border-radius: var(--border-radius-sm);
  border: 1px solid #EBEEF5;
  box-shadow: var(--shadow-sm);
}

.table-wrapper :deep(.el-table) {
  border-radius: var(--border-radius-sm);
}

.table-wrapper :deep(.el-table th.el-table__cell) {
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%) !important;
  font-weight: 700;
  color: #303133;
}

.table-wrapper :deep(.el-table tr:hover > td.el-table__cell) {
  background-color: #ECF5FF !important;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: var(--spacing-lg) 0 var(--spacing-md);
}

/* ==================== 预览卡片增强 ==================== */
.preview-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.preview-card-enhanced {
  background: transparent !important;
  box-shadow: none !important;
}

.preview-empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-welcome {
  padding: var(--spacing-xl);
  text-align: center;
}

.welcome-illustration {
  margin-bottom: var(--spacing-xl);
  display: flex;
  justify-content: center;
}

.welcome-icon-bg {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
  animation: float 3s ease-in-out infinite;
}

.welcome-title {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 var(--spacing-sm) 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.welcome-desc {
  font-size: 14px;
  color: #909399;
  line-height: 1.6;
  margin: 0 0 var(--spacing-xl) 0;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-xl);
  text-align: left;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius-sm);
  border: 1px solid #EBEEF5;
  transition: all 0.3s ease;
}

.feature-item:hover {
  transform: translateX(4px);
  box-shadow: var(--shadow-sm);
  border-color: #409EFF;
}

.feature-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.feature-text {
  flex: 1;
}

.feature-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 2px;
}

.feature-desc {
  font-size: 12px;
  color: #909399;
}

.tip-card {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  background: linear-gradient(135deg, #FFF8E6 0%, #FFF4D9 100%);
  border-radius: var(--border-radius-sm);
  border: 1px solid #FFE4B3;
  color: #909399;
  font-size: 13px;
}

.preview-body-enhanced {
  padding: var(--spacing-xl);
}

/* 项目摘要卡片 */
.project-summary-card {
  background: white;
  border-radius: var(--border-radius);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-md);
  border: 1px solid #E4E7ED;
  margin-bottom: var(--spacing-lg);
}

.summary-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-lg);
  border-bottom: 2px solid #F2F6FC;
}

.summary-info {
  flex: 1;
}

.summary-title {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}

.summary-id {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}

.summary-stats {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius-sm);
}

.summary-stat-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex: 1;
}

.stat-icon-wrapper {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
}

.stat-icon-wrapper.stat-blue {
  background: linear-gradient(135deg, #409EFF 0%, #66b1ff 100%);
}

.stat-icon-wrapper.stat-green {
  background: linear-gradient(135deg, #67C23A 0%, #85ce61 100%);
}

.stat-detail {
  flex: 1;
}

.stat-detail .stat-number {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.stat-detail .stat-text {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.summary-stat-divider {
  width: 1px;
  height: 40px;
  background: #E4E7ED;
}

.resource-preview-list {
  margin-bottom: var(--spacing-lg);
}

.preview-list-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: var(--spacing-md);
}

.preview-type-items {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.type-item {
  display: grid;
  grid-template-columns: 100px 1fr auto;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-sm) 0;
}

.type-bar {
  height: 8px;
  border-radius: 4px;
  transition: width 0.6s ease;
}

.type-requirement {
  background: linear-gradient(90deg, #409EFF 0%, #66b1ff 100%);
}

.type-ui {
  background: linear-gradient(90deg, #E6A23C 0%, #F0C78A 100%);
}

.type-api {
  background: linear-gradient(90deg, #67C23A 0%, #85ce61 100%);
}

.type-label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
}

.type-count {
  font-size: 14px;
  font-weight: 700;
  color: #303133;
}

.next-action-card {
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #ECF5FF 0%, #D9ECFF 100%);
  border-radius: var(--border-radius);
  border: 2px solid #B3D8FF;
  text-align: center;
}

.action-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  color: #409EFF;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: var(--spacing-md);
}

.next-btn-large {
  width: 100%;
  border-radius: 10px !important;
  font-size: 15px !important;
  font-weight: 700 !important;
  padding: 14px 20px !important;
  background: linear-gradient(135deg, #409EFF 0%, #66b1ff 100%) !important;
  border: none !important;
  transition: all 0.3s ease !important;
}

.next-btn-large:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.4) !important;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid #EBEEF5;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
}

.preview-header .el-icon {
  color: var(--primary-color);
  font-size: 20px;
}

.preview-body {
  flex: 1;
  padding: var(--spacing-lg);
  overflow-y: auto;
  background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
}

/* ==================== 信息项 ==================== */
.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) 0;
  border-bottom: 1px solid #F2F6FC;
  transition: all 0.3s ease;
}

.info-item:hover {
  background: #FAFAFA;
  padding-left: var(--spacing-sm);
  padding-right: var(--spacing-sm);
  margin-left: calc(-1 * var(--spacing-sm));
  margin-right: calc(-1 * var(--spacing-sm));
  border-radius: 6px;
}

.info-item:last-child {
  border-bottom: none;
}

.info-item .label {
  color: #909399;
  font-size: 14px;
  font-weight: 500;
}

.info-item .value {
  color: #303133;
  font-weight: 600;
  font-size: 14px;
}

.info-item .value.highlight {
  color: var(--primary-color);
  font-weight: 700;
}

/* ==================== 下一步按钮 ==================== */
.next-step-hint {
  margin-top: var(--spacing-xl);
  padding-top: var(--spacing-lg);
  border-top: 2px solid #E4E7ED;
  text-align: center;
}

.next-step-hint .el-button {
  width: 100%;
  border-radius: 10px;
  font-weight: 700;
  font-size: 15px;
  padding: 14px 20px;
  background: linear-gradient(135deg, #409EFF 0%, #66b1ff 100%);
  border: none;
  transition: all 0.3s ease;
}

.next-step-hint .el-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.4);
}

/* ==================== 资源详情 ==================== */
.resource-detail-card {
  text-align: center;
  padding: var(--spacing-lg) 0;
}

.detail-icon {
  margin-bottom: var(--spacing-lg);
}

.detail-name {
  font-size: 17px;
  font-weight: 700;
  color: #303133;
  margin-bottom: var(--spacing-md);
}

.detail-meta {
  margin-bottom: var(--spacing-lg);
}

.detail-stats {
  display: flex;
  justify-content: center;
  gap: var(--spacing-xl);
  margin-top: var(--spacing-lg);
}

.stat-item {
  text-align: center;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
  font-weight: 500;
}

.stat-value {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

/* ==================== 提取统计 ==================== */
.stats-skeleton {
  padding: var(--spacing-lg);
}

.extract-stats {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.stat-card {
  text-align: center;
  padding: var(--spacing-xl);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: var(--border-radius);
  color: #fff;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.35);
  position: relative;
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
  animation: shimmer 3s infinite;
  will-change: transform;
}

@keyframes shimmer {
  0% { transform: rotate(0deg) translateZ(0); }
  100% { transform: rotate(360deg) translateZ(0); }
}

.stat-card .stat-number {
  font-size: 52px;
  font-weight: 800;
  line-height: 1.2;
  position: relative;
  z-index: 1;
}

.stat-card .stat-label {
  font-size: 15px;
  opacity: 0.95;
  margin-top: var(--spacing-sm);
  font-weight: 600;
  position: relative;
  z-index: 1;
}

/* 优先级分布 */
.distribution-title {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
  margin-bottom: var(--spacing-md);
  padding-left: var(--spacing-sm);
  border-left: 3px solid #409EFF;
}

.distribution-items {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.dist-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius-sm);
  border: 1px solid #EBEEF5;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.dist-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
}

.dist-item.high {
  border-left: 3px solid #F56C6C;
}

.dist-item.high::before {
  background: #F56C6C;
}

.dist-item.medium {
  border-left: 3px solid #E6A23C;
}

.dist-item.medium::before {
  background: #E6A23C;
}

.dist-item.low {
  border-left: 3px solid #909399;
}

.dist-item.low::before {
  background: #909399;
}

.dist-item:hover {
  transform: translateX(4px);
  box-shadow: var(--shadow-sm);
}

.dist-count {
  font-size: 24px;
  font-weight: 800;
  color: #303133;
}

.dist-label {
  font-size: 13px;
  color: #909399;
  font-weight: 600;
}

/* 模块分布 */
.module-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.module-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px var(--spacing-md);
  font-size: 13px;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: 6px;
  border: 1px solid #EBEEF5;
  transition: all 0.3s ease;
}

.module-item:hover {
  background: #ECF5FF;
  border-color: #B3D8FF;
  transform: translateX(4px);
}

.module-name {
  color: #606266;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.module-count {
  font-weight: 700;
  color: var(--primary-color);
  font-size: 15px;
}

/* ==================== 操作指南 ==================== */
.guide-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-xl);
}

.guide-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  font-size: 14px;
  color: #606266;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius-sm);
  border: 1px solid #EBEEF5;
  transition: all 0.3s ease;
}

.guide-item:hover {
  transform: translateX(4px);
  box-shadow: var(--shadow-sm);
  border-color: #409EFF;
}

.quick-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
  padding-top: var(--spacing-lg);
  border-top: 2px solid #E4E7ED;
}

.quick-stat-item {
  text-align: center;
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #ECF5FF 0%, #D9ECFF 100%);
  border-radius: var(--border-radius-sm);
  border: 2px solid #B3D8FF;
  transition: all 0.3s ease;
}

.quick-stat-item:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}

.qs-label {
  display: block;
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
  font-weight: 600;
}

.qs-value {
  display: block;
  font-size: 28px;
  font-weight: 800;
  color: #303133;
}

.qs-value.highlight {
  color: var(--primary-color);
}

/* ==================== 空状态 ==================== */
.empty-hint {
  padding: var(--spacing-xxl) 0;
  text-align: center;
}

.empty-icon,
.ready-icon {
  margin-bottom: var(--spacing-lg);
}

.waiting-state {
  padding: var(--spacing-xxl) 0;
  text-align: center;
}

/* ==================== 对话框 ==================== */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-md);
}

.dialog-footer .el-button {
  border-radius: 8px;
  font-weight: 600;
  padding: 10px 20px;
  transition: all 0.3s ease;
}

.dialog-footer .el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

/* ==================== 过渡动画 ==================== */
.slide-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(1, 0.5, 0.8, 1);
}

.slide-fade-enter-from {
  transform: translateX(30px);
  opacity: 0;
}

.slide-fade-leave-to {
  transform: translateX(-30px);
  opacity: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: all 0.4s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

/* ==================== 响应式适配 ==================== */
@media (max-width: 1200px) {
  .right-panel {
    width: 360px;
  }

  .info-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .main-content {
    flex-direction: column;
  }

  .right-panel {
    width: 100%;
    order: -1;
  }

  .steps-wrapper {
    padding: var(--spacing-lg);
  }

  .steps-wrapper :deep(.el-steps--simple) {
    padding: 0;
  }

  .left-panel,
  .right-panel {
    width: 100%;
  }

  .resource-item {
    flex-wrap: wrap;
  }

  .resource-action {
    width: 100%;
    text-align: right;
    margin-top: var(--spacing-md);
  }

  .batch-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .batch-info,
  .action-buttons {
    width: 100%;
    justify-content: center;
  }

  .page-header h2 {
    font-size: 20px;
  }

  .info-grid {
    grid-template-columns: 1fr 1fr;
  }

  .project-card-footer {
    flex-direction: column;
  }

  .workflow-steps {
    flex-wrap: wrap;
  }

  .guide-title {
    font-size: 22px;
  }

  .illustration-circle {
    width: 110px;
    height: 110px;
  }

  .welcome-icon-bg {
    width: 100px;
    height: 100px;
  }
}
</style>
