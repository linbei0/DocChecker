import type {
  FormatRule,
  RuleExtractionTrace,
  UnsupportedRequirement,
} from '@/entities/ruleset/model'

export type FeedbackGroupId = 'llm' | 'conflict' | 'unsupported' | 'scope'

export interface FeedbackGroup {
  id: FeedbackGroupId
  label: string
  count: number
  description: string
  nextAction: string
}

export function buildFeedbackGroups(
  rules: FormatRule[],
  unsupportedRequirements: UnsupportedRequirement[],
): FeedbackGroup[] {
  return [
    {
      id: 'llm',
      label: 'LLM 不确定',
      count: rules.filter(isLlmUncertainRule).length + unsupportedRequirements.filter(isLlmIssue).length,
      description: '候选来自 LLM，但 schema、置信度或表达方式不足以直接执行。',
      nextAction: '优先看原始要求是否清楚；若清楚但仍失败，调整 prompt 或 manifest 示例。',
    },
    {
      id: 'conflict',
      label: '规则冲突',
      count: rules.filter(isConflictRule).length + unsupportedRequirements.filter(isConflictIssue).length,
      description: '同一检查目标出现多个互斥期望值，系统不能替你决定采用哪一个。',
      nextAction: '保留权威来源或高置信证据，删除或禁用其余冲突项。',
    },
    {
      id: 'unsupported',
      label: '系统暂不支持',
      count: unsupportedRequirements.filter(isUnsupportedIssue).length,
      description: '规则语义已经识别，但当前 facts、解析器或 checker 还没有执行能力。',
      nextAction: '导出能力缺口，按 category 和 reason_code 统计后补 extractor/checker/tests。',
    },
    {
      id: 'scope',
      label: '字段支持但目标范围不确定',
      count: rules.filter(isScopeUncertainRule).length + unsupportedRequirements.filter(isScopeIssue).length,
      description: '字段本身可检查，但适用范围、选择器或语义边界还需要人工确认。',
      nextAction: '确认 target scope 和 selector，必要时把自然语言改成更明确的规则表达。',
    },
  ]
}

export function buildTraceDiagnosis(trace: RuleExtractionTrace | null | undefined): string[] {
  if (!trace?.stats) return []
  const items: string[] = []
  if (trace.stats.llm_rejected_count > 0) {
    items.push('LLM 输出被 schema 拒绝，优先检查 prompt 约束和返回 JSON 结构。')
  }
  if (trace.stats.unsupported_field_count > 0) {
    items.push('存在 unsupported field，优先补 capability manifest 或 checker 字段 resolver。')
  }
  if (trace.stats.conflict_count > 0) {
    items.push('存在规则冲突，优先确认规范来源优先级，而不是继续补解析规则。')
  }
  if (trace.stats.auto_checkable_conversion_rate < 0.5) {
    items.push('自动转化率偏低，优先查看 needs confirmation 是否集中在同一类 scope。')
  }
  return items
}

export function buildUnsupportedBacklogPayload(params: {
  draftId: string
  generatedAt: string
  rules: FormatRule[]
  unsupportedRequirements: UnsupportedRequirement[]
  extractionTrace: RuleExtractionTrace | null | undefined
}) {
  const feedbackGroups = buildFeedbackGroups(params.rules, params.unsupportedRequirements)
  return {
    draft_id: params.draftId,
    generated_at: params.generatedAt,
    summary: {
      feedback_groups: feedbackGroups.map(({ id, label, count }) => ({ id, label, count })),
      trace_diagnosis: buildTraceDiagnosis(params.extractionTrace),
    },
    unsupported_requirements: params.unsupportedRequirements,
    extraction_trace: params.extractionTrace ?? null,
  }
}

function isLlmUncertainRule(rule: FormatRule) {
  return (
    rule.capability_status === 'needs_confirmation' &&
    rule.source.evidence_type === 'llm_candidate'
  )
}

function isConflictRule(rule: FormatRule) {
  return rule.capability_status === 'conflict'
}

function isScopeUncertainRule(rule: FormatRule) {
  return (
    rule.capability_status === 'needs_confirmation' &&
    rule.source.evidence_type !== 'llm_candidate'
  )
}

function isLlmIssue(requirement: UnsupportedRequirement) {
  return ['invalid_llm_response', 'llm_not_configured'].includes(requirement.reason_code || '')
}

function isConflictIssue(requirement: UnsupportedRequirement) {
  return requirement.capability_status === 'conflict'
}

function isUnsupportedIssue(requirement: UnsupportedRequirement) {
  if (isLlmIssue(requirement) || isConflictIssue(requirement) || isScopeIssue(requirement)) {
    return false
  }
  return (
    requirement.capability_status === 'unsupported' ||
    ['missing_checker', 'unsupported_field', 'out_of_scope'].includes(
      requirement.reason_code || '',
    )
  )
}

function isScopeIssue(requirement: UnsupportedRequirement) {
  return (
    requirement.capability_status === 'needs_confirmation' &&
    requirement.reason_code === 'ambiguous_requirement'
  )
}
