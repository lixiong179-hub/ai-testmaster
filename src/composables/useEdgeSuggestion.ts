import { ref } from 'vue'
import type { Edge } from '@vue-flow/core'
import { type FlowEditorNode, getNodeData } from '@/composables/useFlowEditor'

export interface EdgeSuggestion {
  sourceNodeId: string
  sourceScreenName: string
  targetNodeId: string
  targetScreenName: string
  reason: string
  matchScore: number
  accepted: boolean
}

interface UIElement {
  name?: string
  label?: string
  text?: string
  button_text?: string
  link_text?: string
  navigation?: string
  target_page?: string
}

const extractKeywords = (name: string): string[] => {
  const cleaned = name
    .replace(/[页面屏幕窗口]/g, '')
    .replace(/[（）()[\]【】]/g, ' ')
    .trim()
  const parts = cleaned.split(/[\s\-_/]+/).filter((p) => p.length > 0)
  return parts.length > 0 ? parts : [name]
}

const computeNameSimilarity = (sourceName: string, candidateName: string): number => {
  if (!sourceName || !candidateName) return 0
  const sLower = sourceName.toLowerCase()
  const cLower = candidateName.toLowerCase()
  if (sLower === cLower) return 1
  if (sLower.includes(cLower) || cLower.includes(sLower)) return 0.8
  const srcKw = extractKeywords(sourceName)
  const candKw = extractKeywords(candidateName)
  const matchCount = srcKw.filter((kw) =>
    candKw.some((ck) => ck.includes(kw) || kw.includes(ck))
  ).length
  const totalKw = Math.max(srcKw.length, candKw.length, 1)
  const score = matchCount / totalKw
  if (matchCount >= 2) return Math.max(score, 0.6)
  return Math.max(score, 0)
}

const collectElementTexts = (elements: UIElement[]): string[] => {
  const texts: string[] = []
  elements.forEach((el) => {
    const fields = [
      el.name,
      el.label,
      el.text,
      el.button_text,
      el.link_text,
      el.navigation,
      el.target_page,
    ]
    fields.forEach((f) => {
      if (f && typeof f === 'string' && f.trim().length > 0) {
        texts.push(f.trim())
      }
    })
  })
  return texts
}

export const useEdgeSuggestion = () => {
  const suggestions = ref<EdgeSuggestion[]>([])

  const analyzeTransitions = (nodes: FlowEditorNode[], existingEdges: Edge[]): EdgeSuggestion[] => {
    const results: EdgeSuggestion[] = []
    const edgePairs = new Set<string>()
    existingEdges.forEach((e) => {
      edgePairs.add(`${e.source}->${e.target}`)
    })

    for (const sourceNode of nodes) {
      const sourceData = getNodeData(sourceNode)
      const sourceName = sourceData.screen_name || ''
      const elements = (sourceData.ui_spec_elements || []) as UIElement[]
      const elementTexts = collectElementTexts(elements)

      for (const targetNode of nodes) {
        if (sourceNode.id === targetNode.id) continue
        const pairKey = `${sourceNode.id}->${targetNode.id}`
        if (edgePairs.has(pairKey)) continue
        const targetName = getNodeData(targetNode).screen_name || ''
        const nameScore = computeNameSimilarity(sourceName, targetName)
        let elementScore = 0
        let matchedText = ''
        for (const text of elementTexts) {
          const tScore = computeNameSimilarity(text, targetName)
          if (tScore > elementScore) {
            elementScore = tScore
            matchedText = text
          }
        }
        const bestScore = Math.max(nameScore, elementScore)
        if (bestScore >= 0.5) {
          const reason =
            elementScore >= nameScore && elementScore >= 0.5
              ? `元素 "${matchedText}" 与目标页面 "${targetName}" 匹配`
              : `页面名称 "${sourceName}" 与 "${targetName}" 相似`
          results.push({
            sourceNodeId: sourceNode.id,
            sourceScreenName: sourceName || '未命名',
            targetNodeId: targetNode.id,
            targetScreenName: targetName || '未命名',
            reason,
            matchScore: Math.round(bestScore * 100),
            accepted: false,
          })
        }
      }
    }

    results.sort((a, b) => b.matchScore - a.matchScore)
    return results
  }

  const runAnalysis = (nodes: FlowEditorNode[], existingEdges: Edge[]) => {
    suggestions.value = analyzeTransitions(nodes, existingEdges)
    return suggestions.value
  }

  const clearSuggestions = () => {
    suggestions.value = []
  }

  return {
    suggestions,
    runAnalysis,
    clearSuggestions,
  }
}
