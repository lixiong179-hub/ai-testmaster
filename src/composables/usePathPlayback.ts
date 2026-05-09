import { ref, computed } from 'vue'
import type { Edge } from '@vue-flow/core'
import {
  type FlowEditorNode,
  getNodeData,
  getMainNodesInOrder,
  computeBranchChildren,
} from '@/composables/useFlowEditor'

export interface PlayStep {
  nodeId: string
  screenName: string
  flowType: string
  isBranchChoice: boolean
  branchOptions: Array<{ edgeId: string; targetNodeId: string; targetName: string }>
  nextEdgeId: string | null
}

export const usePathPlayback = () => {
  const isPlaying = ref(false)
  const playPath = ref<PlayStep[]>([])
  const currentPlayIndex = ref(0)
  const showBranchChoice = ref(false)

  const currentPlayNodeId = computed(() => {
    if (!isPlaying.value || playPath.value.length === 0) return null
    return playPath.value[currentPlayIndex.value]?.nodeId ?? null
  })

  const currentPlayEdgeId = computed(() => {
    if (!isPlaying.value || playPath.value.length === 0) return null
    return playPath.value[currentPlayIndex.value]?.nextEdgeId ?? null
  })

  const hasPrevStep = computed(() => currentPlayIndex.value > 0)
  const hasNextStep = computed(() => currentPlayIndex.value < playPath.value.length - 1)

  const findNextEdge = (
    edges: Edge[],
    currentNodeId: string,
    nextNodeId: string | null
  ): string | null => {
    if (!nextNodeId) return null
    const edge = edges.find((e) => e.source === currentNodeId && e.target === nextNodeId)
    return edge?.id ?? null
  }

  const buildMainPath = (nodes: FlowEditorNode[], edges: Edge[]): PlayStep[] => {
    const mainNodes = getMainNodesInOrder(nodes)
    if (mainNodes.length === 0) return []
    const steps: PlayStep[] = []
    for (let i = 0; i < mainNodes.length; i += 1) {
      const node = mainNodes[i]
      const data = getNodeData(node)
      const branches = computeBranchChildren(nodes, edges, node.id)
      const nextMainId = i < mainNodes.length - 1 ? mainNodes[i + 1].id : null
      const nextEdgeId = findNextEdge(edges, node.id, nextMainId)
      steps.push({
        nodeId: node.id,
        screenName: data.screen_name || '未命名页面',
        flowType: data.flow_type || 'main',
        isBranchChoice: branches.length > 0,
        branchOptions: branches.map((b) => ({
          edgeId: b.edge.id,
          targetNodeId: b.node.id,
          targetName: getNodeData(b.node).screen_name || '未命名',
        })),
        nextEdgeId,
      })
    }
    return steps
  }

  const startPlayback = (nodes: FlowEditorNode[], edges: Edge[]) => {
    playPath.value = buildMainPath(nodes, edges)
    if (playPath.value.length === 0) return
    isPlaying.value = true
    currentPlayIndex.value = 0
    showBranchChoice.value = false
  }

  const stopPlayback = () => {
    isPlaying.value = false
    playPath.value = []
    currentPlayIndex.value = 0
    showBranchChoice.value = false
  }

  const goToStep = (index: number) => {
    if (index < 0 || index >= playPath.value.length) return
    currentPlayIndex.value = index
    showBranchChoice.value = false
  }

  const nextStep = () => {
    const currentStep = playPath.value[currentPlayIndex.value]
    if (!currentStep) return
    if (
      currentStep.isBranchChoice &&
      currentStep.branchOptions.length > 0 &&
      !showBranchChoice.value
    ) {
      showBranchChoice.value = true
      return
    }
    if (currentPlayIndex.value < playPath.value.length - 1) {
      currentPlayIndex.value += 1
      showBranchChoice.value = false
    }
  }

  const prevStep = () => {
    if (currentPlayIndex.value > 0) {
      currentPlayIndex.value -= 1
      showBranchChoice.value = false
    }
  }

  const followBranch = (targetNodeId: string, edges: Edge[], nodes: FlowEditorNode[]) => {
    const currentStep = playPath.value[currentPlayIndex.value]
    if (!currentStep) return
    const nextMainIdx = currentPlayIndex.value + 1
    const nextMainNodeId =
      nextMainIdx < playPath.value.length ? playPath.value[nextMainIdx].nodeId : null
    const branchEdgeToMain = nextMainNodeId
      ? findNextEdge(edges, targetNodeId, nextMainNodeId)
      : null
    const branchNode = nodes.find((n) => n.id === targetNodeId)
    const branchBranches = branchNode ? computeBranchChildren(nodes, edges, targetNodeId) : []
    const newSteps: PlayStep[] = [
      ...playPath.value.slice(0, currentPlayIndex.value + 1),
      {
        nodeId: targetNodeId,
        screenName:
          currentStep.branchOptions.find((b) => b.targetNodeId === targetNodeId)?.targetName ??
          '分支',
        flowType: 'branch',
        isBranchChoice: branchBranches.length > 0,
        branchOptions: branchBranches.map((b) => ({
          edgeId: b.edge.id,
          targetNodeId: b.node.id,
          targetName: getNodeData(b.node).screen_name || '未命名',
        })),
        nextEdgeId: branchEdgeToMain,
      },
    ]
    if (nextMainNodeId) {
      const nextMainStep = playPath.value[nextMainIdx]
      newSteps.push({
        ...nextMainStep,
        nodeId: nextMainNodeId,
      } as PlayStep)
    }
    playPath.value = newSteps
    currentPlayIndex.value = currentPlayIndex.value + 1
    showBranchChoice.value = false
  }

  const getStepInfo = (): string => {
    if (!isPlaying.value || playPath.value.length === 0) return ''
    return `第 ${currentPlayIndex.value + 1} / ${playPath.value.length} 步`
  }

  return {
    isPlaying,
    playPath,
    currentPlayIndex,
    currentPlayNodeId,
    currentPlayEdgeId,
    showBranchChoice,
    hasPrevStep,
    hasNextStep,
    startPlayback,
    stopPlayback,
    goToStep,
    nextStep,
    prevStep,
    followBranch,
    getStepInfo,
  }
}
