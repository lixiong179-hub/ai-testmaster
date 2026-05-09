import type { TestPoint } from '@/types/testPoint'
import type { FlowEditorNode } from '@/composables/useFlowEditor'
import { getNodeData } from '@/composables/useFlowEditor'

export const useTestPointLink = () => {
  const matchScore = (testPoint: TestPoint, screenName: string): number => {
    if (!screenName) return 0
    const sLower = screenName.toLowerCase()
    const matches = [testPoint.module, testPoint.function, testPoint.point]
    let score = 0
    matches.forEach((field) => {
      if (!field) return
      const fLower = field.toLowerCase()
      if (sLower.includes(fLower) || fLower.includes(sLower)) {
        score += 0.5
      }
    })
    return Math.min(score, 1)
  }

  const getRelatedScreenIds = (
    selectedTestPointIds: number[],
    testPoints: TestPoint[],
    nodes: FlowEditorNode[]
  ): Set<number> => {
    const relatedScreenIds = new Set<number>()
    if (selectedTestPointIds.length === 0 || testPoints.length === 0) {
      return relatedScreenIds
    }
    const selectedPoints = testPoints.filter((tp) => selectedTestPointIds.includes(tp.id))
    nodes.forEach((node) => {
      const data = getNodeData(node)
      const screenName = data.screen_name || ''
      const screenId = data.screen_id
      for (const tp of selectedPoints) {
        if (matchScore(tp, screenName) >= 0.5) {
          relatedScreenIds.add(screenId)
          break
        }
      }
    })
    return relatedScreenIds
  }

  const getRelatedTestPointIds = (
    selectedNodeIds: string[],
    nodes: FlowEditorNode[],
    testPoints: TestPoint[]
  ): number[] => {
    if (selectedNodeIds.length === 0 || testPoints.length === 0) return []
    const results: number[] = []
    const selectedNodes = nodes.filter((n) => selectedNodeIds.includes(n.id))
    selectedNodes.forEach((node) => {
      const screenName = getNodeData(node).screen_name || ''
      testPoints.forEach((tp) => {
        if (matchScore(tp, screenName) >= 0.5 && !results.includes(tp.id)) {
          results.push(tp.id)
        }
      })
    })
    return results
  }

  const matchScreenName = (testPoint: TestPoint, screenName: string): boolean =>
    matchScore(testPoint, screenName) >= 0.5

  return {
    getRelatedScreenIds,
    getRelatedTestPointIds,
    matchScreenName,
  }
}
