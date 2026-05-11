import type { FormatRule, UnsupportedRequirement } from '@/entities/ruleset/model'
import { categoryLabel, targetScopeLabel } from './ruleConfirmText'

export type ReviewFilter = 'all' | 'auto' | 'confirmation' | 'conflict' | 'llm' | 'unsupported'

export type RuleReviewItem = {
  id: string
  kind: 'rule'
  title: string
  rule: FormatRule
}

export type UnsupportedReviewItem = {
  id: string
  kind: 'unsupported'
  title: string
  requirement: UnsupportedRequirement
}

export type ReviewItem = RuleReviewItem | UnsupportedReviewItem
export type ReviewGroup = {
  id: string
  title: string
  subtitle: string
  items: ReviewItem[]
  enabledCount: number
  totalRuleCount: number
}

export const FILTER_OPTIONS: Array<{ id: ReviewFilter; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'auto', label: '可自动校验' },
  { id: 'confirmation', label: '字段支持但需确认' },
  { id: 'conflict', label: '规则冲突' },
  { id: 'llm', label: 'LLM 不确定' },
  { id: 'unsupported', label: '系统暂不支持' },
]

export function buildReviewItems(
  rules: FormatRule[],
  unsupportedRequirements: UnsupportedRequirement[],
): ReviewItem[] {
  const ruleItems: RuleReviewItem[] = dedupeBy(
    rules.map((rule) => ({
      id: `rule:${rule.id}`,
      kind: 'rule' as const,
      title: rule.target.selector || rule.target.scope,
      rule,
    })),
    (item) => item.id,
  )
  const ruleSourceKeys = new Set(
    ruleItems.map((item) =>
      reviewSourceKey(item.rule.category, item.rule.source.location, item.rule.source.excerpt),
    ),
  )
  const unsupportedItems: UnsupportedReviewItem[] = dedupeBy(
    unsupportedRequirements
      .filter(
        (requirement) =>
          !ruleSourceKeys.has(
            reviewSourceKey(requirement.category, requirement.location, requirement.excerpt),
          ),
      )
      .map((requirement, index) => ({
        id: `unsupported:${requirement.category}:${requirement.location || index}:${requirement.excerpt}`,
        kind: 'unsupported' as const,
        title: requirement.target_scope || requirement.location || requirement.category,
        requirement,
      })),
    (item) =>
      reviewSourceKey(
        item.requirement.category,
        item.requirement.location,
        item.requirement.excerpt,
      ),
  )
  return [...ruleItems, ...unsupportedItems]
}

export function buildReviewGroups(items: ReviewItem[]): ReviewGroup[] {
  const groups = new Map<string, ReviewGroup>()
  for (const item of items) {
    const key = reviewGroupKey(item)
    const existing = groups.get(key)
    if (existing) {
      existing.items.push(item)
      if (item.kind === 'rule') {
        existing.totalRuleCount += 1
        if (item.rule.enabled !== false) existing.enabledCount += 1
      }
      continue
    }
    groups.set(key, {
      id: key,
      title: reviewGroupTitle(item),
      subtitle: reviewGroupSubtitle(item),
      items: [item],
      enabledCount: item.kind === 'rule' && item.rule.enabled !== false ? 1 : 0,
      totalRuleCount: item.kind === 'rule' ? 1 : 0,
    })
  }
  return [...groups.values()]
}

function reviewGroupKey(item: ReviewItem): string {
  if (item.kind === 'unsupported') {
    return `unsupported:${item.requirement.target_scope || item.requirement.category}`
  }
  const scope = normalizedRuleScope(item.rule)
  return `rule:${scope}`
}

function reviewGroupTitle(item: ReviewItem): string {
  if (item.kind === 'unsupported') {
    return targetScopeLabel(item.requirement.target_scope || item.requirement.category)
  }
  return targetScopeLabel(normalizedRuleScope(item.rule))
}

function reviewGroupSubtitle(item: ReviewItem): string {
  if (item.kind === 'unsupported') {
    return '暂不支持或需补充能力的规范要求'
  }
  const rule = item.rule
  return [categoryLabel(rule.category), rule.target.selector]
    .filter(Boolean)
    .join(' / ')
}

function normalizedRuleScope(rule: FormatRule): string {
  if (rule.target.scope === 'document' && isBodySelector(rule.target.selector)) {
    return 'body.paragraph'
  }
  if (rule.target.scope === 'paragraph' && isBodySelector(rule.target.selector)) {
    return 'body.paragraph'
  }
  if (rule.target.scope.startsWith('heading.')) return rule.target.scope
  if (rule.target.scope === 'heading' && rule.target.selector) {
    const level = headingSelectorLevel(rule.target.selector)
    if (level) return `heading.${level}`
  }
  return rule.target.scope
}

function isBodySelector(selector?: string | null) {
  return ['正文', '正文段落', 'body', 'body.paragraph'].includes(selector || '')
}

function headingSelectorLevel(selector: string) {
  if (selector.includes('一级标题') || selector === 'Heading 1') return 1
  if (selector.includes('二级标题') || selector === 'Heading 2') return 2
  if (selector.includes('三级标题') || selector === 'Heading 3') return 3
  const match = selector.match(/Heading\s*([1-6])/i)
  return match ? Number(match[1]) : null
}

function dedupeBy<T>(items: T[], keyOf: (item: T) => string): T[] {
  const seen = new Set<string>()
  const result: T[] = []
  for (const item of items) {
    const key = keyOf(item)
    if (seen.has(key)) continue
    seen.add(key)
    result.push(item)
  }
  return result
}

function reviewSourceKey(
  category: string,
  location: string | null | undefined,
  excerpt: string,
) {
  return [
    category,
    location || '',
    excerpt.replace(/\s+/g, ' ').trim(),
  ].join('|')
}

export function matchesFilter(item: ReviewItem, filter: ReviewFilter): boolean {
  if (filter === 'all') return true
  if (item.kind === 'unsupported') {
    if (filter === 'conflict') return item.requirement.capability_status === 'conflict'
    if (filter === 'llm') {
      return ['invalid_llm_response', 'llm_not_configured'].includes(
        item.requirement.reason_code || '',
      )
    }
    if (filter === 'confirmation') {
      return item.requirement.capability_status === 'needs_confirmation'
    }
    return filter === 'unsupported' && item.requirement.capability_status === 'unsupported'
  }
  if (filter === 'auto') return item.rule.capability_status === 'auto_checkable'
  if (filter === 'confirmation') {
    return (
      item.rule.capability_status === 'needs_confirmation' &&
      item.rule.source.evidence_type !== 'llm_candidate'
    )
  }
  if (filter === 'conflict') return item.rule.capability_status === 'conflict'
  if (filter === 'llm') {
    return (
      item.rule.capability_status === 'needs_confirmation' &&
      item.rule.source.evidence_type === 'llm_candidate'
    )
  }
  return false
}

export function countByFilter(items: ReviewItem[], filter: ReviewFilter): number {
  return items.filter((item) => matchesFilter(item, filter)).length
}
