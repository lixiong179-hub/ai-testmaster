import { defineStore } from 'pinia';
import type { TestPoint } from '@/types/testPoint';
import type { TestPointListResponse } from '@/api/testPoint';
import { testPointApi } from '@/api/testPoint';

export const useAnalysisStore = defineStore('analysis', {
  state: () => ({
    // 分析进度
    progress: 0,
    // 分析状态：idle, analyzing, success, failed
    status: 'idle' as 'idle' | 'analyzing' | 'success' | 'failed',
    // 分析消息
    message: '',
    // 测试点列表
    testPoints: [] as TestPoint[],
    // 当前项目ID
    currentProjectId: 0
  }),

  getters: {
    // 按模块分组的测试点
    testPointsByModule: (state) => {
      const grouped: Record<string, TestPoint[]> = {};
      state.testPoints.forEach(point => {
        if (!grouped[point.module]) {
          grouped[point.module] = [];
        }
        grouped[point.module].push(point);
      });
      return grouped;
    },

    // 按优先级分组的测试点
    testPointsByPriority: (state) => {
      const grouped: Record<number, TestPoint[]> = {
        1: [],
        2: [],
        3: []
      };
      state.testPoints.forEach(point => {
        const key = point.priority as number;
        if (!grouped[key]) {
          grouped[key] = [];
        }
        grouped[key].push(point);
      });
      return grouped;
    }
  },

  actions: {
    // 开始分析
    async startAnalysis(projectId: number) {
      this.currentProjectId = projectId;
      this.status = 'analyzing';
      this.progress = 0;
      this.message = '开始分析需求...';

      try {
        const generator = await testPointApi.analyze({ project_id: projectId });
        
        for await (const progress of generator) {
          this.progress = progress.progress;
          this.message = progress.message || '分析中...';
          
          if (progress.data) {
            this.testPoints = progress.data.map(tp => ({
              ...tp,
              create_time: String(tp.create_time)
            }));
          }
        }

        this.status = 'success';
        this.message = '分析完成';
      } catch (error) {
        console.error('分析失败:', error);
        this.status = 'failed';
        this.message = '分析失败，请检查DeepSeek配置';
      }
    },

    // 获取测试点列表
    async fetchTestPoints(projectId: number, params?: {
      module?: string;
      priority?: number;
    }) {
      try {
        const apiData: TestPointListResponse = await testPointApi.getList(projectId, params);
        this.testPoints = (apiData.items || []).map(tp => ({
          ...tp,
          create_time: String(tp.create_time)
        }));
        this.currentProjectId = projectId;
      } catch (error) {
        console.error('获取测试点失败:', error);
        this.testPoints = [];
      }
    },

    // 重置状态
    resetState() {
      this.progress = 0;
      this.status = 'idle';
      this.message = '';
      this.testPoints = [];
      this.currentProjectId = 0;
    }
  }
});
