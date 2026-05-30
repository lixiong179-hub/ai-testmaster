import request from '@/utils/request'

export const listRefreshSuggestions = (
    projectId: number,
    page: number = 1,
    pageSize: number = 20,
    suggestionStatus?: string,
    reviewStatus?: string
) => {
    const params: Record<string, unknown> = { page, page_size: pageSize }
    if (suggestionStatus) params.suggestion_status = suggestionStatus
    if (reviewStatus) params.review_status = reviewStatus
    return request.get(
        `/api/v1/caseRefresh/projects/${projectId}/refresh-suggestions`,
        { params }
    )
}

export const reviewRefreshSuggestion = (
    suggestionId: number,
    action: string,
    rejectReason?: string
) => {
    return request.post(
        `/api/v1/caseRefresh/refresh-suggestions/${suggestionId}/review`,
        { action, reject_reason: rejectReason }
    )
}

export const scanStaleCases = (projectId: number) => {
    return request.post(
        `/api/v1/caseRefresh/projects/${projectId}/scan-stale-cases`
    )
}

export const autoRefreshCases = (projectId: number, maxCases: number = 10) => {
    return request.post(
        `/api/v1/caseRefresh/projects/${projectId}/auto-refresh`,
        null,
        { params: { max_cases: maxCases } }
    )
}

export const getRefreshSuggestionsStats = (projectId: number) => {
    return request.get(
        `/api/v1/caseRefresh/projects/${projectId}/refresh-suggestions/stats`
    )
}
