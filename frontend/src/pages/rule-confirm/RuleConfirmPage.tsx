import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  ChevronDown,
  Download,
  Edit2,
  XCircle,
} from 'lucide-react'
import { Button } from '@/shared/ui/Button'
import { SeverityBadge } from '@/shared/ui/SeverityBadge'
import { cn } from '@/shared/lib/utils'
import type { FormatRule, UnsupportedRequirement } from '@/entities/ruleset/model'
import {
  useDraftRuleSetQuery,
  usePublishDraftRuleSetMutation,
  useUpdateDraftRuleSetMutation,
} from '@/features/rulesets/hooks'
import { useCreateCheckTaskMutation } from '@/features/check-tasks/hooks'

type ReviewFilter = 'all' | 'auto' | 'confirmation' | 'conflict' | 'llm' | 'unsupported'

type RuleReviewItem = {
  id: string
  kind: 'rule'
  title: string
  rule: FormatRule
}

type UnsupportedReviewItem = {
  id: string
  kind: 'unsupported'
  title: string
  requirement: UnsupportedRequirement
}

type ReviewItem = RuleReviewItem | UnsupportedReviewItem

export function RuleConfirmPage() {
  const { taskId: draftId = '' } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const { data: draft, isLoading } = useDraftRuleSetQuery(draftId)
  const updateDraftMutation = useUpdateDraftRuleSetMutation(draftId)
  const publishDraftMutation = usePublishDraftRuleSetMutation()
  const createCheckTaskMutation = useCreateCheckTaskMutation()
  const [rules, setRules] = useState<FormatRule[]>([])
  const [expandedItemId, setExpandedItemId] = useState<string | null>(null)
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null)
  const [expectationText, setExpectationText] = useState('')
  const [activeFilter, setActiveFilter] = useState<ReviewFilter>('all')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (draft) {
      setRules([...draft.rules, ...(draft.suggested_rules ?? [])])
    }
  }, [draft])

  const toggleRule = (id: string) => {
    setRules((prev) =>
      prev.map((rule) => {
        if (rule.id !== id) return rule
        const nextEnabled = !(rule.enabled !== false)
        return {
          ...rule,
          enabled: nextEnabled,
          capability_status:
            nextEnabled &&
              (rule.capability_status === 'needs_confirmation' ||
                rule.capability_status === 'conflict')
              ? 'auto_checkable'
              : rule.capability_status,
          confirmation_required:
            nextEnabled &&
              (rule.capability_status === 'needs_confirmation' ||
                rule.capability_status === 'conflict')
              ? false
              : rule.confirmation_required,
        }
      }),
    )
  }

  const setRulesEnabled = (
    enabled: boolean,
    predicate: (rule: FormatRule) => boolean = () => true,
  ) => {
    setRules((prev) =>
      prev.map((rule) =>
        predicate(rule)
          ? {
            ...rule,
            enabled,
            capability_status:
              enabled &&
                (rule.capability_status === 'needs_confirmation' ||
                  rule.capability_status === 'conflict')
                ? 'auto_checkable'
                : rule.capability_status,
            confirmation_required:
              enabled &&
                (rule.capability_status === 'needs_confirmation' ||
                  rule.capability_status === 'conflict')
                ? false
                : rule.confirmation_required,
          }
          : rule,
      ),
    )
  }

  const startEditing = (rule: FormatRule) => {
    setEditingRuleId(rule.id)
    setExpandedItemId(`rule:${rule.id}`)
    setExpectationText(JSON.stringify(rule.expectation, null, 2))
  }

  const saveRuleEdit = (ruleId: string) => {
    try {
      const parsed = JSON.parse(expectationText) as Record<string, unknown>
      setRules((prev) =>
        prev.map((rule) => (rule.id === ruleId ? { ...rule, expectation: parsed } : rule)),
      )
      setEditingRuleId(null)
      setError(null)
    } catch {
      setError('期望值必须是合法 JSON。')
    }
  }

  const handleConfirmAndCheck = async () => {
    if (!draft) return
    try {
      setError(null)
      const autoRules = rules.filter((rule) => rule.capability_status === 'auto_checkable')
      const suggestedRules = rules.filter(
        (rule) => rule.capability_status !== 'auto_checkable',
      )
      await updateDraftMutation.mutateAsync({
        rules: autoRules,
        suggested_rules: suggestedRules,
        name: draft.name,
      })
      const ruleset = await publishDraftMutation.mutateAsync(draft.id)
      const task = await createCheckTaskMutation.mutateAsync({
        document_id: draft.document_id,
        ruleset_id: ruleset.id,
      })
      navigate(`/checks/${task.id}/progress`)
    } catch (err) {
      setError('确认规则失败：' + (err instanceof Error ? err.message : '未知错误'))
    }
  }

  const exportUnsupportedBacklog = () => {
    if (!draft) return
    const payload = {
      draft_id: draft.id,
      generated_at: new Date().toISOString(),
      unsupported_requirements: draft.unsupported_requirements ?? [],
      extraction_trace: draft.extraction_trace ?? null,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: 'application/json;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `docchecker-unsupported-${draft.id}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-7xl items-center justify-center px-4 py-20 text-sm text-neutral-500 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary-300 border-t-primary-600" />
          加载候选规则中...
        </div>
      </div>
    )
  }

  if (!draft) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-20 text-center sm:px-6 lg:px-8">
        <div className="mx-auto max-w-md">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-neutral-100">
            <AlertCircle className="h-8 w-8 text-neutral-400" />
          </div>
          <h2 className="mt-6 text-lg font-semibold text-neutral-900">候选规则集不存在</h2>
          <p className="mt-2 text-sm text-neutral-500">该规则集可能已过期或已被删除。</p>
          <Link
            to="/checks/new"
            className="mt-6 inline-flex items-center text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            返回新建检查
          </Link>
        </div>
      </div>
    )
  }

  const summary = draft.extraction_summary
  const unsupportedRequirements = draft.unsupported_requirements ?? []
  const reviewItems = buildReviewItems(rules, unsupportedRequirements)
  const visibleItems = reviewItems.filter((item) => matchesFilter(item, activeFilter))
  const visibleRules = visibleItems
    .filter((item): item is RuleReviewItem => item.kind === 'rule')
    .map((item) => item.rule)

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-2xl">
          <h1 className="text-xl font-bold tracking-tight text-neutral-900 sm:text-2xl">确认规则</h1>
          <p className="mt-1.5 text-sm leading-relaxed text-neutral-500">
            所有规则诊断、人工确认和不可校验说明都在同一工作台里完成。
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Button variant="secondary" onClick={() => navigate(-1)}>
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            返回上一步
          </Button>
          <Button
            onClick={handleConfirmAndCheck}
            disabled={rules.length === 0}
            isLoading={
              updateDraftMutation.isPending ||
              publishDraftMutation.isPending ||
              createCheckTaskMutation.isPending
            }
          >
            确认并检查
            <ArrowRight className="ml-1.5 h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-danger-100 bg-danger-50 px-4 py-3.5 text-sm text-danger-700 shadow-sm animate-in slide-in-from-top-1">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger-500" />
          <span className="leading-relaxed">{error}</span>
        </div>
      )}

      {/* Parse Warnings */}
      {draft.parse_warnings.length > 0 && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-warning-100 bg-warning-50 px-4 py-3.5 text-sm text-warning-800 shadow-sm animate-in slide-in-from-top-1">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warning-500" />
          <span className="leading-relaxed">{draft.parse_warnings.join('；')}</span>
        </div>
      )}

      {/* Summary Metrics */}
      {summary && (
        <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:gap-4">
          <SummaryMetric label="识别到要求" value={summary.total_requirements} icon={<CheckCircle className="h-4 w-4 text-neutral-400" />} />
          <SummaryMetric label="可自动校验" value={summary.structured_rules} tone="success" icon={<CheckCircle className="h-4 w-4 text-success-500" />} />
          <SummaryMetric
            label="需人工确认"
            value={summary.needs_confirmation_rules ?? summary.low_confidence_rules}
            tone="warning"
            icon={<AlertCircle className="h-4 w-4 text-warning-500" />}
          />
          <SummaryMetric label="当前不可校验" value={summary.unsupported_requirements} tone="danger" icon={<XCircle className="h-4 w-4 text-danger-500" />} />
        </div>
      )}

      {draft.extraction_trace?.stats && (
        <div className="mb-8 rounded-2xl border border-neutral-200/80 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-base font-semibold text-neutral-900">抽取诊断</h2>
              <p className="mt-1 text-xs leading-relaxed text-neutral-500">
                这里区分 LLM 不确定、规则冲突和系统暂不支持，便于判断下一步该调 prompt 还是补检查器。
              </p>
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={exportUnsupportedBacklog}
              disabled={unsupportedRequirements.length === 0}
            >
              <Download className="mr-1.5 h-4 w-4" />
              导出能力缺口
            </Button>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <TraceMetric label="本地候选" value={draft.extraction_trace.stats.local_candidate_count} />
            <TraceMetric label="LLM 候选" value={draft.extraction_trace.stats.llm_candidate_count} />
            <TraceMetric label="LLM 拒绝" value={draft.extraction_trace.stats.llm_rejected_count} />
            <TraceMetric label="字段不支持" value={draft.extraction_trace.stats.unsupported_field_count} />
            <TraceMetric
              label="自动转化率"
              value={`${Math.round(draft.extraction_trace.stats.auto_checkable_conversion_rate * 100)}%`}
            />
          </div>
        </div>
      )}

      {/* Main Workbench */}
      <div className="overflow-hidden rounded-2xl border border-neutral-200/80 bg-white shadow-sm">
        {/* Workbench Header */}
        <div className="border-b border-neutral-100 px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-base font-semibold text-neutral-900">规则诊断与确认工作台</h2>
              <p className="mt-1 text-xs leading-relaxed text-neutral-500">
                在同一列表里处理自动规则、人工确认项和当前不可校验项。
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRulesEnabled(true, (rule) => visibleRules.includes(rule))}
                disabled={visibleRules.length === 0}
                className="text-success-600 hover:bg-success-50 hover:text-success-700"
              >
                <CheckCircle className="mr-1.5 h-4 w-4" />
                启用当前筛选
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRulesEnabled(false, (rule) => visibleRules.includes(rule))}
                disabled={visibleRules.length === 0}
                className="text-danger-600 hover:bg-danger-50 hover:text-danger-700"
              >
                <XCircle className="mr-1.5 h-4 w-4" />
                禁用当前筛选
              </Button>
            </div>
          </div>

          {/* Filter Tabs */}
          <div className="mt-5 flex flex-wrap gap-2">
            {FILTER_OPTIONS.map((option) => (
              <FilterPill
                key={option.id}
                active={activeFilter === option.id}
                onClick={() => setActiveFilter(option.id)}
                label={option.label}
                count={countByFilter(reviewItems, option.id)}
              />
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-100 bg-neutral-50/80">
                <th className="w-[72px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-500 sm:px-6">
                  状态
                </th>
                <th className="w-[100px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-500 sm:px-6">
                  类别
                </th>
                <th className="w-[110px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-500 sm:px-6">
                  能力状态
                </th>
                <th className="w-[140px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-500 sm:px-6">
                  适用范围
                </th>
                <th className="min-w-[240px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-500 sm:px-6">
                  内容
                </th>
                <th className="w-[90px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-500 sm:px-6">
                  严重度
                </th>
                <th className="w-[72px] px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-neutral-500 sm:px-6">
                  操作
                </th>
              </tr>
            </thead>
            {visibleItems.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={7} className="px-6 py-16 text-center">
                    <div className="flex flex-col items-center gap-3 text-neutral-400">
                      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-neutral-100">
                        <AlertCircle className="h-6 w-6 text-neutral-300" />
                      </div>
                      <p className="text-sm">当前筛选下没有项目。</p>
                    </div>
                  </td>
                </tr>
              </tbody>
            ) : (
              visibleItems.map((item) =>
                item.kind === 'rule' ? (
                  <RuleRow
                    key={item.id}
                    rule={item.rule}
                    expanded={expandedItemId === item.id}
                    editing={editingRuleId === item.rule.id}
                    expectationText={expectationText}
                    onExpectationTextChange={setExpectationText}
                    onToggle={() => toggleRule(item.rule.id)}
                    onExpand={() => setExpandedItemId(expandedItemId === item.id ? null : item.id)}
                    onEdit={() => startEditing(item.rule)}
                    onCancelEdit={() => setEditingRuleId(null)}
                    onSaveEdit={() => saveRuleEdit(item.rule.id)}
                    onSeverityChange={(severity) =>
                      setRules((prev) =>
                        prev.map((rule) =>
                          rule.id === item.rule.id ? { ...rule, severity } : rule,
                        ),
                      )
                    }
                  />
                ) : (
                  <UnsupportedRow
                    key={item.id}
                    requirement={item.requirement}
                    expanded={expandedItemId === item.id}
                    onExpand={() => setExpandedItemId(expandedItemId === item.id ? null : item.id)}
                  />
                ),
              )
            )}
          </table>
        </div>
      </div>
    </div>
  )
}

const FILTER_OPTIONS: Array<{ id: ReviewFilter; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'auto', label: '可自动校验' },
  { id: 'confirmation', label: '字段支持但需确认' },
  { id: 'conflict', label: '规则冲突' },
  { id: 'llm', label: 'LLM 不确定' },
  { id: 'unsupported', label: '系统暂不支持' },
]

function buildReviewItems(
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
        id: `unsupported:${requirement.location || index}:${requirement.excerpt}`,
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

function matchesFilter(item: ReviewItem, filter: ReviewFilter): boolean {
  if (filter === 'all') return true
  if (item.kind === 'unsupported') {
    if (filter === 'conflict') return item.requirement.capability_status === 'conflict'
    if (filter === 'llm') {
      return ['invalid_llm_response', 'llm_not_configured'].includes(
        item.requirement.reason_code || '',
      )
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

function countByFilter(items: ReviewItem[], filter: ReviewFilter): number {
  return items.filter((item) => matchesFilter(item, filter)).length
}

/* ─── Sub-components ─── */

function SummaryMetric({
  label,
  value,
  tone = 'neutral',
  icon,
}: {
  label: string
  value: number
  tone?: 'neutral' | 'success' | 'warning' | 'danger'
  icon?: React.ReactNode
}) {
  const toneStyles = {
    neutral: {
      value: 'text-neutral-900',
      iconBg: 'bg-neutral-100',
    },
    success: {
      value: 'text-success-600',
      iconBg: 'bg-success-50',
    },
    warning: {
      value: 'text-warning-600',
      iconBg: 'bg-warning-50',
    },
    danger: {
      value: 'text-danger-600',
      iconBg: 'bg-danger-50',
    },
  }[tone]

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-neutral-200/80 bg-white p-4 shadow-sm transition-all duration-200 hover:shadow-md hover:border-neutral-300 sm:p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-neutral-500">{label}</p>
          <p className={cn('mt-2 text-3xl font-bold tracking-tight tabular-nums', toneStyles.value)}>
            {value}
          </p>
        </div>
        {icon && (
          <div className={cn('flex h-8 w-8 items-center justify-center rounded-lg transition-colors', toneStyles.iconBg)}>
            {icon}
          </div>
        )}
      </div>
    </div>
  )
}

function TraceMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-neutral-100 bg-neutral-50/70 px-3.5 py-3">
      <p className="text-[11px] font-medium text-neutral-500">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-neutral-900">{value}</p>
    </div>
  )
}

function FilterPill({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean
  onClick: () => void
  label: string
  count: number
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'inline-flex items-center rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all duration-200',
        active
          ? 'border-primary-300 bg-primary-50 text-primary-700 shadow-sm'
          : 'border-neutral-200 bg-white text-neutral-600 hover:border-neutral-300 hover:bg-neutral-50',
      )}
    >
      {label}
      <span
        className={cn(
          'ml-1.5 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full px-1 text-[10px] font-semibold tabular-nums',
          active ? 'bg-primary-100 text-primary-700' : 'bg-neutral-100 text-neutral-500',
        )}
      >
        {count}
      </span>
    </button>
  )
}

function ToggleSwitch({
  enabled,
  onToggle,
}: {
  enabled: boolean
  onToggle: () => void
}) {
  return (
    <button
      onClick={onToggle}
      role="switch"
      aria-checked={enabled}
      className={cn(
        'relative inline-flex h-[22px] w-10 items-center rounded-full transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/40 focus-visible:ring-offset-2',
        enabled ? 'bg-primary-600' : 'bg-neutral-300',
      )}
    >
      <span
        className={cn(
          'inline-block h-[18px] w-[18px] transform rounded-full bg-white shadow-sm transition-transform duration-200 ease-out',
          enabled ? 'translate-x-[18px]' : 'translate-x-[2px]',
        )}
      />
    </button>
  )
}

function UnsupportedRow({
  requirement,
  expanded,
  onExpand,
}: {
  requirement: UnsupportedRequirement
  expanded: boolean
  onExpand: () => void
}) {
  const contentRef = useRef<HTMLTableCellElement>(null)

  return (
    <tbody className="border-b border-neutral-100 last:border-b-0">
      <tr className="group transition-colors duration-150 hover:bg-neutral-50/80">
        <td className="px-4 py-3.5 sm:px-6">
          <span className="inline-flex items-center rounded-full bg-neutral-100 px-2.5 py-1 text-[11px] font-medium text-neutral-500">
            不可启用
          </span>
        </td>
        <td className="px-4 py-3.5 text-sm font-medium text-neutral-900 sm:px-6">
          {requirement.category}
        </td>
        <td className="px-4 py-3.5 sm:px-6">
          <span className="inline-flex items-center rounded-full bg-warning-50 px-2.5 py-1 text-[11px] font-medium text-warning-700">
            {capabilityStatusLabel(requirement.capability_status || 'unsupported')}
          </span>
        </td>
        <td className="px-4 py-3.5 text-sm text-neutral-600 sm:px-6">
          <span className="line-clamp-1">{requirement.target_scope || requirement.location || '未定位'}</span>
        </td>
        <td className="px-4 py-3.5 text-sm text-neutral-700 sm:px-6">
          <span className="line-clamp-2">{requirement.excerpt}</span>
        </td>
        <td className="px-4 py-3.5 sm:px-6">
          <span className="inline-flex items-center rounded-full border border-neutral-200 bg-white px-2.5 py-1 text-[11px] font-medium text-neutral-500">
            说明
          </span>
        </td>
        <td className="px-4 py-3.5 text-right sm:px-6">
          <button
            onClick={onExpand}
            className={cn(
              'inline-flex items-center justify-center rounded-lg p-1.5 text-neutral-400 transition-all duration-150 hover:bg-neutral-100 hover:text-neutral-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/30',
              expanded && 'bg-neutral-100 text-neutral-600',
            )}
            aria-label={expanded ? '收起详情' : '展开详情'}
          >
            <ChevronDown className={cn('h-4 w-4 transition-transform duration-200', expanded && 'rotate-180')} />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td
            ref={contentRef}
            colSpan={7}
            className="border-t border-neutral-100 bg-neutral-50/60 px-4 py-5 sm:px-6"
          >
            <div className="grid gap-5 lg:grid-cols-2">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-1.5 rounded-full bg-neutral-400" />
                  <p className="text-xs font-semibold text-neutral-700">原始要求</p>
                </div>
                <p className="rounded-xl border border-neutral-200/80 bg-white p-4 text-sm leading-relaxed text-neutral-700 shadow-sm">
                  {requirement.excerpt}
                </p>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500">
                  <span>来源位置：{requirement.location || '未定位'}</span>
                  {requirement.reason_code && (
                    <span>诊断类型：{reasonCodeLabel(requirement.reason_code)}</span>
                  )}
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-1.5 rounded-full bg-warning-400" />
                  <p className="text-xs font-semibold text-neutral-700">当前状态说明</p>
                </div>
                <div className="rounded-xl border border-warning-100 bg-white p-4 shadow-sm">
                  <p className="text-sm leading-relaxed text-neutral-700">{requirement.reason}</p>
                  <p className="mt-3 text-xs leading-relaxed text-warning-700">
                    {unsupportedActionHint(requirement)}
                  </p>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </tbody>
  )
}

function RuleRow({
  rule,
  expanded,
  editing,
  expectationText,
  onExpectationTextChange,
  onToggle,
  onExpand,
  onEdit,
  onCancelEdit,
  onSaveEdit,
  onSeverityChange,
}: {
  rule: FormatRule
  expanded: boolean
  editing: boolean
  expectationText: string
  onExpectationTextChange: (value: string) => void
  onToggle: () => void
  onExpand: () => void
  onEdit: () => void
  onCancelEdit: () => void
  onSaveEdit: () => void
  onSeverityChange: (value: FormatRule['severity']) => void
}) {
  const isEnabled = rule.enabled !== false
  const expectationStr = Object.entries(rule.expectation)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(', ')

  return (
    <tbody className="border-b border-neutral-100 last:border-b-0">
      <tr
        className={cn(
          'group transition-colors duration-150',
          isEnabled ? 'hover:bg-neutral-50/80' : 'bg-neutral-50/40 hover:bg-neutral-50/60',
        )}
      >
        <td className="px-4 py-3.5 sm:px-6">
          <ToggleSwitch enabled={isEnabled} onToggle={onToggle} />
        </td>
        <td className="px-4 py-3.5 text-sm font-medium text-neutral-900 sm:px-6">
          {rule.category}
        </td>
        <td className="px-4 py-3.5 sm:px-6">
          <CapabilityBadge status={rule.capability_status || 'auto_checkable'} />
        </td>
        <td className="px-4 py-3.5 text-sm text-neutral-600 sm:px-6">
          <span className="line-clamp-1">{rule.target.selector || rule.target.scope}</span>
        </td>
        <td className="px-4 py-3.5 text-sm text-neutral-700 sm:px-6">
          <span className={cn('line-clamp-2', !isEnabled && 'text-neutral-400')} title={expectationStr}>
            {expectationStr}
          </span>
        </td>
        <td className="px-4 py-3.5 sm:px-6">
          <SeverityBadge severity={rule.severity} />
        </td>
        <td className="px-4 py-3.5 text-right sm:px-6">
          <button
            onClick={onExpand}
            className={cn(
              'inline-flex items-center justify-center rounded-lg p-1.5 text-neutral-400 transition-all duration-150 hover:bg-neutral-100 hover:text-neutral-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/30',
              expanded && 'bg-neutral-100 text-neutral-600',
            )}
            aria-label={expanded ? '收起详情' : '编辑规则'}
          >
            {expanded ? (
              <ChevronDown className="h-4 w-4 transition-transform duration-200" />
            ) : (
              <Edit2 className="h-4 w-4" />
            )}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} className="border-t border-neutral-100 bg-neutral-50/60 px-4 py-5 sm:px-6">
            <div className="grid gap-5 lg:grid-cols-2">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-1.5 rounded-full bg-primary-400" />
                  <p className="text-xs font-semibold text-neutral-700">来源片段</p>
                </div>
                <p className="rounded-xl border border-neutral-200/80 bg-white p-4 text-sm leading-relaxed text-neutral-700 shadow-sm">
                  {rule.source.excerpt || '无来源片段'}
                </p>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500">
                  <span>来源位置：{rule.source.location || '未定位'}</span>
                  <span>置信度：{Math.round((rule.confidence ?? 1) * 100)}%</span>
                  <span>证据类型：{evidenceTypeLabel(rule.source.evidence_type || 'explicit_text')}</span>
                </div>
                {rule.capability_status === 'needs_confirmation' && (
                  <div className="flex items-start gap-2.5 rounded-xl bg-warning-50 px-4 py-3 text-xs leading-relaxed text-warning-700">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warning-500" />
                    这条规则需要你人工确认后再启用。编辑期望值并打开左侧开关后，它才会参与正式检查。
                  </div>
                )}
              </div>
              <div className="space-y-4">
                <label className="block space-y-2">
                  <span className="text-xs font-semibold text-neutral-700">严重度</span>
                  <select
                    value={rule.severity}
                    onChange={(event) =>
                      onSeverityChange(event.target.value as FormatRule['severity'])
                    }
                    className="block w-full rounded-xl border border-neutral-200 bg-white px-3.5 py-2.5 text-sm text-neutral-800 shadow-sm transition-colors focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                  >
                    <option value="blocker">阻断</option>
                    <option value="major">严重</option>
                    <option value="minor">一般</option>
                    <option value="info">提示</option>
                  </select>
                </label>
                {editing ? (
                  <div className="space-y-2">
                    <span className="text-xs font-semibold text-neutral-700">期望值 JSON</span>
                    <textarea
                      value={expectationText}
                      onChange={(event) => onExpectationTextChange(event.target.value)}
                      rows={5}
                      className="w-full rounded-xl border border-neutral-200 bg-white p-3.5 font-mono text-xs leading-relaxed text-neutral-800 shadow-sm transition-colors focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                    />
                    <div className="flex gap-2 pt-1">
                      <Button size="sm" onClick={onSaveEdit}>
                        保存
                      </Button>
                      <Button size="sm" variant="secondary" onClick={onCancelEdit}>
                        取消
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button size="sm" variant="secondary" onClick={onEdit}>
                    <Edit2 className="mr-1.5 h-3.5 w-3.5" />
                    编辑期望值
                  </Button>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </tbody>
  )
}

function CapabilityBadge({ status }: { status: string }) {
  const styles =
    status === 'needs_confirmation'
      ? 'bg-warning-50 text-warning-700 border-warning-100'
      : status === 'auto_checkable'
        ? 'bg-success-50 text-success-700 border-success-100'
        : status === 'conflict'
          ? 'bg-danger-50 text-danger-700 border-danger-100'
          : 'bg-neutral-100 text-neutral-600 border-neutral-200'

  return (
    <span className={cn('inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium', styles)}>
      {capabilityStatusLabel(status)}
    </span>
  )
}

function reasonCodeLabel(code: string) {
  return (
    {
      missing_checker: '缺少检查器',
      ambiguous_requirement: '语义不明确',
      out_of_scope: '超出范围',
      llm_not_configured: 'LLM 未配置',
      invalid_llm_response: 'LLM 响应无效',
      unsupported_field: '字段暂不支持',
    }[code] || code
  )
}

function capabilityStatusLabel(status: string) {
  return (
    {
      auto_checkable: '可自动校验',
      needs_confirmation: '建议确认',
      unsupported: '当前不支持',
      conflict: '证据冲突',
      parse_error: '解析失败',
    }[status] || status
  )
}

function evidenceTypeLabel(type: string) {
  return (
    {
      explicit_text: '文字规则',
      comment_anchor: '批注锚点',
      exemplar_format: '样例格式',
      style_cluster: '样式簇',
      table_cell: '表格单元格',
      llm_candidate: 'LLM 候选',
      manual_text: '手动文本',
      template: '模板',
    }[type] || type
  )
}

function unsupportedActionHint(requirement: UnsupportedRequirement) {
  if (requirement.capability_status === 'conflict') {
    return '这类项通常对应同目标的冲突规则。请优先在"建议人工确认"筛选里确认最终可执行规则。'
  }
  if (requirement.capability_status === 'needs_confirmation') {
    return '这类项本身还没有形成可执行规则，不能直接启用，需要先补充更明确的规则表达。'
  }
  return '这类项当前没有对应检查器，暂时不能直接人工确认成自动检查规则。'
}
