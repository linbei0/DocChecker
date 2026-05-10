import { Fragment, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  ChevronDown,
  Download,
  Edit2,
  PlusCircle,
  Trash2,
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
import {
  buildFeedbackGroups,
  buildTraceDiagnosis,
  buildUnsupportedBacklogPayload,
  type FeedbackGroup,
} from './ruleReviewDiagnostics'

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
type EditableValueKind = 'string' | 'number' | 'boolean' | 'list' | 'json'

type ReviewGroup = {
  id: string
  title: string
  subtitle: string
  items: ReviewItem[]
  enabledCount: number
  totalRuleCount: number
}

type ExpectationDraftField = {
  key: string
  value: string
  kind: EditableValueKind
}

type ExpectationDraftPatch = Partial<ExpectationDraftField>

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
  const [expectationDraft, setExpectationDraft] = useState<ExpectationDraftField[]>([])
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
    setExpectationDraft(createExpectationDraft(rule.expectation))
  }

  const saveRuleEdit = (ruleId: string) => {
    const parsed = serializeExpectationDraft(expectationDraft)
    if (!parsed.ok) {
      setError(parsed.error)
      return
    }
    setRules((prev) =>
      prev.map((rule) => (rule.id === ruleId ? { ...rule, expectation: parsed.value } : rule)),
    )
    setEditingRuleId(null)
    setError(null)
  }

  const updateExpectationDraftField = (index: number, patch: ExpectationDraftPatch) => {
    setExpectationDraft((prev) =>
      prev.map((field, currentIndex) =>
        currentIndex === index ? { ...field, ...patch } : field,
      ),
    )
  }

  const addExpectationDraftField = () => {
    setExpectationDraft((prev) => [...prev, { key: '', value: '', kind: 'string' }])
  }

  const removeExpectationDraftField = (index: number) => {
    setExpectationDraft((prev) => prev.filter((_, currentIndex) => currentIndex !== index))
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
    const payload = buildUnsupportedBacklogPayload({
      draftId: draft.id,
      generatedAt: new Date().toISOString(),
      rules,
      unsupportedRequirements: draft.unsupported_requirements ?? [],
      extractionTrace: draft.extraction_trace,
    })
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

  if (draft.status === 'processing') {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-neutral-200 bg-white p-8 shadow-sm">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary-50">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-200 border-t-primary-600" />
            </div>
            <div className="min-w-0 flex-1">
              <h1 className="text-lg font-semibold text-neutral-950">正在生成候选规则</h1>
              <p className="mt-2 text-sm leading-relaxed text-neutral-600">
                规范文档已经进入后台抽取流程。本页会自动刷新，生成完成后进入规则确认工作台。
              </p>
              <div className="mt-5 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm text-neutral-600">
                {draft.parse_warnings[0] || '规则抽取正在后台执行。'}
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button variant="secondary" onClick={() => navigate('/checks/new')}>
                  <ArrowLeft className="mr-1.5 h-4 w-4" />
                  返回新建检查
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (draft.status === 'failed') {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-danger-100 bg-white p-8 shadow-sm">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-danger-50">
              <AlertCircle className="h-6 w-6 text-danger-600" />
            </div>
            <div className="min-w-0 flex-1">
              <h1 className="text-lg font-semibold text-neutral-950">候选规则生成失败</h1>
              <p className="mt-2 text-sm leading-relaxed text-neutral-600">
                后台抽取流程返回了明确错误，当前草稿不会进入发布步骤。
              </p>
              <div className="mt-5 whitespace-pre-wrap break-words rounded-xl border border-danger-100 bg-danger-50 px-4 py-3 text-sm text-danger-700">
                {draft.error || '未知错误'}
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button variant="secondary" onClick={() => navigate('/checks/new')}>
                  <ArrowLeft className="mr-1.5 h-4 w-4" />
                  返回新建检查
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const summary = draft.extraction_summary
  const unsupportedRequirements = draft.unsupported_requirements ?? []
  const reviewItems = buildReviewItems(rules, unsupportedRequirements)
  const feedbackGroups = buildFeedbackGroups(rules, unsupportedRequirements)
  const traceDiagnosis = buildTraceDiagnosis(draft.extraction_trace)
  const visibleItems = reviewItems.filter((item) => matchesFilter(item, activeFilter))
  const visibleRules = visibleItems
    .filter((item): item is RuleReviewItem => item.kind === 'rule')
    .map((item) => item.rule)
  const visibleGroups = buildReviewGroups(visibleItems)

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
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            <TraceMetric
              label="处理规范块"
              value={draft.extraction_trace.stats.processed_block_count ?? '-'}
            />
            <TraceMetric label="抽取批次" value={draft.extraction_trace.stats.batch_count ?? '-'} />
            <TraceMetric label="本地候选" value={draft.extraction_trace.stats.local_candidate_count} />
            <TraceMetric label="LLM 候选" value={draft.extraction_trace.stats.llm_candidate_count} />
            <TraceMetric
              label="候选拒绝"
              value={
                draft.extraction_trace.stats.rejected_candidate_count ??
                draft.extraction_trace.stats.llm_rejected_count
              }
            />
            <TraceMetric label="字段不支持" value={draft.extraction_trace.stats.unsupported_field_count} />
            <TraceMetric
              label="自动转化率"
              value={`${Math.round(draft.extraction_trace.stats.auto_checkable_conversion_rate * 100)}%`}
            />
          </div>
          {traceDiagnosis.length > 0 && (
            <div className="mt-4 rounded-xl border border-neutral-100 bg-neutral-50/70 px-4 py-3">
              <p className="text-xs font-semibold text-neutral-700">诊断指向</p>
              <div className="mt-2 grid gap-2 text-xs leading-relaxed text-neutral-600 lg:grid-cols-2">
                {traceDiagnosis.map((item) => (
                  <div key={item} className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary-400" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="mb-8 grid gap-3 lg:grid-cols-4">
        {feedbackGroups.map((group) => (
          <FeedbackGroupCard
            key={group.id}
            group={group}
            active={activeFilter === group.id || (group.id === 'scope' && activeFilter === 'confirmation')}
            onClick={() => setActiveFilter(group.id === 'scope' ? 'confirmation' : group.id)}
          />
        ))}
      </div>

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
            {visibleGroups.length === 0 ? (
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
              visibleGroups.map((group) => (
                <Fragment key={group.id}>
                  <RuleGroupHeader group={group} />
                  {group.items.map((item) =>
                    item.kind === 'rule' ? (
                      <RuleRow
                        key={item.id}
                        rule={item.rule}
                        expanded={expandedItemId === item.id}
                        editing={editingRuleId === item.rule.id}
                        expectationDraft={expectationDraft}
                        onToggle={() => toggleRule(item.rule.id)}
                        onExpand={() =>
                          setExpandedItemId(expandedItemId === item.id ? null : item.id)
                        }
                        onEdit={() => startEditing(item.rule)}
                        onCancelEdit={() => setEditingRuleId(null)}
                        onSaveEdit={() => saveRuleEdit(item.rule.id)}
                        onDraftFieldChange={updateExpectationDraftField}
                        onAddDraftField={addExpectationDraftField}
                        onRemoveDraftField={removeExpectationDraftField}
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
                        onExpand={() =>
                          setExpandedItemId(expandedItemId === item.id ? null : item.id)
                        }
                      />
                    ),
                  )}
                </Fragment>
              ))
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

function buildReviewGroups(items: ReviewItem[]): ReviewGroup[] {
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

function matchesFilter(item: ReviewItem, filter: ReviewFilter): boolean {
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

function FeedbackGroupCard({
  group,
  active,
  onClick,
}: {
  group: FeedbackGroup
  active: boolean
  onClick: () => void
}) {
  const tone =
    group.id === 'unsupported'
      ? 'border-danger-100 bg-danger-50/40 text-danger-700'
      : group.id === 'conflict'
        ? 'border-warning-100 bg-warning-50/50 text-warning-700'
        : 'border-neutral-200 bg-white text-neutral-700'

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-2xl border p-4 text-left shadow-sm transition-all duration-150 hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary-500/30',
        tone,
        active && 'ring-2 ring-primary-400/30',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-neutral-900">{group.label}</p>
          <p className="mt-1 text-xs leading-relaxed text-neutral-500">{group.description}</p>
        </div>
        <span className="rounded-full bg-white/80 px-2.5 py-1 text-sm font-semibold tabular-nums text-neutral-900">
          {group.count}
        </span>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-neutral-600">{group.nextAction}</p>
    </button>
  )
}

function RuleGroupHeader({ group }: { group: ReviewGroup }) {
  const categories = Array.from(
    new Set(
      group.items.map((item) =>
        item.kind === 'rule' ? categoryLabel(item.rule.category) : categoryLabel(item.requirement.category),
      ),
    ),
  )
  const statusText =
    group.totalRuleCount > 0
      ? `${group.enabledCount}/${group.totalRuleCount} 已启用`
      : `${group.items.length} 条待处理`

  return (
    <tbody>
      <tr className="border-y border-neutral-200 bg-neutral-100/70">
        <td colSpan={7} className="px-4 py-3 sm:px-6">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-neutral-900">{group.title}</span>
                <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-neutral-500 ring-1 ring-neutral-200">
                  {group.items.length} 条规则
                </span>
                <span className="rounded-full bg-primary-50 px-2.5 py-1 text-[11px] font-medium text-primary-700 ring-1 ring-primary-100">
                  {statusText}
                </span>
              </div>
              <p className="mt-1 text-xs text-neutral-500">
                {group.subtitle}
                {categories.length > 0 && ` · ${categories.join('、')}`}
              </p>
            </div>
            <p className="text-xs text-neutral-500">同一适用范围的字体、段落和标题要求已合并展示</p>
          </div>
        </td>
      </tr>
    </tbody>
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
        'inline-flex items-center rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all duration-200 focus-visible:ring-2 focus-visible:ring-primary-500/30',
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
  label,
}: {
  enabled: boolean
  onToggle: () => void
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      role="switch"
      aria-checked={enabled}
      aria-label={label}
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
  expectationDraft,
  onToggle,
  onExpand,
  onEdit,
  onCancelEdit,
  onSaveEdit,
  onDraftFieldChange,
  onAddDraftField,
  onRemoveDraftField,
  onSeverityChange,
}: {
  rule: FormatRule
  expanded: boolean
  editing: boolean
  expectationDraft: ExpectationDraftField[]
  onToggle: () => void
  onExpand: () => void
  onEdit: () => void
  onCancelEdit: () => void
  onSaveEdit: () => void
  onDraftFieldChange: (index: number, patch: ExpectationDraftPatch) => void
  onAddDraftField: () => void
  onRemoveDraftField: (index: number) => void
  onSeverityChange: (value: FormatRule['severity']) => void
}) {
  const isEnabled = rule.enabled !== false
  const expectationStr = formatExpectationSummary(rule.expectation)

  return (
    <tbody className="border-b border-neutral-100 last:border-b-0">
      <tr
        className={cn(
          'group transition-colors duration-150',
          isEnabled ? 'hover:bg-neutral-50/80' : 'bg-neutral-50/40 hover:bg-neutral-50/60',
        )}
      >
        <td className="px-4 py-3.5 sm:px-6">
          <ToggleSwitch
            enabled={isEnabled}
            onToggle={onToggle}
            label={`${isEnabled ? '禁用' : '启用'}规则：${rule.category}，${rule.target.selector || rule.target.scope
              }`}
          />
        </td>
        <td className="px-4 py-3.5 text-sm font-medium text-neutral-900 sm:px-6">
          {categoryLabel(rule.category)}
        </td>
        <td className="px-4 py-3.5 sm:px-6">
          <CapabilityBadge status={rule.capability_status || 'auto_checkable'} />
        </td>
        <td className="px-4 py-3.5 text-sm text-neutral-600 sm:px-6">
          <span className="line-clamp-1">{formatRuleTarget(rule)}</span>
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
                  <p className="text-xs font-semibold text-neutral-700">原文证据</p>
                </div>
                <p className="rounded-xl border border-neutral-200/80 bg-white p-4 text-sm leading-relaxed text-neutral-700 shadow-sm">
                  {rule.source.excerpt || '无来源片段'}
                </p>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500">
                  <span>来源位置：{rule.source.location || '未定位'}</span>
                  <span>置信度：{Math.round((rule.confidence ?? 1) * 100)}%</span>
                  <span>证据类型：{evidenceTypeLabel(rule.source.evidence_type || 'explicit_text')}</span>
                </div>
                <div className="rounded-xl border border-neutral-200/80 bg-white p-4 shadow-sm">
                  <p className="text-xs font-semibold text-neutral-700">系统理解</p>
                  <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                    <DetailTerm label="类别" value={categoryLabel(rule.category)} />
                    <DetailTerm label="影响范围" value={formatRuleTarget(rule)} />
                    <DetailTerm label="期望规则" value={formatExpectationSummary(rule.expectation)} wide />
                  </dl>
                </div>
                {rule.capability_status === 'needs_confirmation' && (
                  <div className="flex items-start gap-2.5 rounded-xl bg-warning-50 px-4 py-3 text-xs leading-relaxed text-warning-700">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warning-500" />
                    这条规则需要先确认语义和期望值。确认后打开左侧开关，它才会参与正式检查。
                  </div>
                )}
              </div>
              <div className="space-y-4">
                <div className="rounded-xl border border-neutral-200/80 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs font-semibold text-neutral-700">可校验性</p>
                    <CapabilityBadge status={rule.capability_status || 'auto_checkable'} />
                  </div>
                  <p className="mt-3 text-xs leading-relaxed text-neutral-600">
                    {capabilityExplanation(rule)}
                  </p>
                </div>
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
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-neutral-700">期望值</span>
                      <Button type="button" size="sm" variant="ghost" onClick={onAddDraftField}>
                        <PlusCircle className="mr-1.5 h-3.5 w-3.5" />
                        添加字段
                      </Button>
                    </div>
                    <ExpectationEditor
                      fields={expectationDraft}
                      onFieldChange={onDraftFieldChange}
                      onRemoveField={onRemoveDraftField}
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
                  <div className="rounded-xl border border-neutral-200/80 bg-white p-4 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold text-neutral-700">期望值</p>
                        <ExpectationPreview expectation={rule.expectation} />
                      </div>
                      <Button size="sm" variant="secondary" onClick={onEdit}>
                        <Edit2 className="mr-1.5 h-3.5 w-3.5" />
                        编辑
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </tbody>
  )
}

function DetailTerm({
  label,
  value,
  wide,
}: {
  label: string
  value: string
  wide?: boolean
}) {
  return (
    <div className={cn('min-w-0', wide && 'sm:col-span-2')}>
      <dt className="text-[11px] font-medium text-neutral-500">{label}</dt>
      <dd className="mt-1 break-words text-neutral-900">{value || '-'}</dd>
    </div>
  )
}

function ExpectationPreview({ expectation }: { expectation: Record<string, unknown> }) {
  const entries = Object.entries(expectation)
  if (entries.length === 0) {
    return <p className="mt-2 text-sm text-neutral-400">未设置期望字段</p>
  }

  return (
    <dl className="mt-3 grid gap-2">
      {entries.map(([key, value]) => (
        <div key={key} className="grid gap-1 text-sm sm:grid-cols-[8rem_1fr]">
          <dt className="min-w-0 text-neutral-500">{fieldLabel(key)}</dt>
          <dd className="min-w-0 break-words text-neutral-900">
            {formatExpectationValue(key, value)}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function ExpectationEditor({
  fields,
  onFieldChange,
  onRemoveField,
}: {
  fields: ExpectationDraftField[]
  onFieldChange: (index: number, patch: ExpectationDraftPatch) => void
  onRemoveField: (index: number) => void
}) {
  if (fields.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-neutral-300 bg-white px-4 py-6 text-center text-sm text-neutral-500">
        当前没有期望字段。
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <datalist id="expectation-field-options">
        {FIELD_OPTIONS.map((field) => (
          <option key={field.key} value={field.key}>
            {field.label}
          </option>
        ))}
      </datalist>
      {fields.map((field, index) => (
        <div
          key={`${field.key || 'new'}-${index}`}
          className="rounded-xl border border-neutral-200 bg-white p-3 shadow-sm"
        >
          <div className="grid gap-3 lg:grid-cols-[1.2fr_8rem_1.4fr_auto]">
            <label className="min-w-0 space-y-1.5">
              <span className="text-[11px] font-medium text-neutral-500">字段</span>
              <input
                list="expectation-field-options"
                value={field.key}
                onChange={(event) => onFieldChange(index, { key: event.target.value })}
                className="h-9 w-full rounded-lg border border-neutral-200 px-3 text-sm text-neutral-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                placeholder="例如 fontSizePt"
              />
              {field.key && (
                <span className="block truncate text-[11px] text-neutral-400">
                  {fieldLabel(field.key)}
                </span>
              )}
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] font-medium text-neutral-500">类型</span>
              <select
                value={field.kind}
                onChange={(event) =>
                  onFieldChange(index, normalizeDraftKindChange(field, event.target.value as EditableValueKind))
                }
                className="h-9 w-full rounded-lg border border-neutral-200 bg-white px-2.5 text-sm text-neutral-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
              >
                <option value="string">文本</option>
                <option value="number">数字</option>
                <option value="boolean">是/否</option>
                <option value="list">列表</option>
                <option value="json">复杂值</option>
              </select>
            </label>
            <ExpectationValueInput
              field={field}
              onChange={(value) => onFieldChange(index, { value })}
            />
            <button
              type="button"
              onClick={() => onRemoveField(index)}
              className="inline-flex h-9 w-9 items-center justify-center self-end rounded-lg text-neutral-400 transition-colors hover:bg-danger-50 hover:text-danger-600"
              aria-label="删除期望字段"
              title="删除期望字段"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

function ExpectationValueInput({
  field,
  onChange,
}: {
  field: ExpectationDraftField
  onChange: (value: string) => void
}) {
  if (field.kind === 'boolean') {
    return (
      <label className="space-y-1.5">
        <span className="text-[11px] font-medium text-neutral-500">值</span>
        <select
          value={field.value}
          onChange={(event) => onChange(event.target.value)}
          className="h-9 w-full rounded-lg border border-neutral-200 bg-white px-2.5 text-sm text-neutral-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
        >
          <option value="true">是</option>
          <option value="false">否</option>
        </select>
      </label>
    )
  }

  if (field.kind === 'json') {
    return (
      <label className="space-y-1.5">
        <span className="text-[11px] font-medium text-neutral-500">复杂值</span>
        <textarea
          value={field.value}
          onChange={(event) => onChange(event.target.value)}
          rows={2}
          className="min-h-9 w-full rounded-lg border border-neutral-200 px-3 py-2 font-mono text-xs text-neutral-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
        />
      </label>
    )
  }

  return (
    <label className="space-y-1.5">
      <span className="text-[11px] font-medium text-neutral-500">
        {field.kind === 'list' ? '值，多个用逗号分隔' : '值'}
      </span>
      <input
        value={field.value}
        type={field.kind === 'number' ? 'number' : 'text'}
        step={field.kind === 'number' ? 'any' : undefined}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-lg border border-neutral-200 px-3 text-sm text-neutral-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
      />
    </label>
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

function createExpectationDraft(expectation: Record<string, unknown>): ExpectationDraftField[] {
  return Object.entries(expectation).map(([key, value]) => ({
    key,
    value: draftValue(value),
    kind: inferValueKind(value),
  }))
}

function serializeExpectationDraft(
  fields: ExpectationDraftField[],
): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  if (fields.length === 0) {
    return { ok: false, error: '至少保留一个期望字段。' }
  }

  const expectation: Record<string, unknown> = {}
  const seen = new Set<string>()
  for (const field of fields) {
    const key = field.key.trim()
    if (!key) return { ok: false, error: '期望值字段名称不能为空。' }
    if (seen.has(key)) return { ok: false, error: `期望值字段重复：${key}` }
    seen.add(key)

    const parsed = parseDraftValue(field)
    if (!parsed.ok) return parsed
    expectation[key] = parsed.value
  }
  return { ok: true, value: expectation }
}

function parseDraftValue(
  field: ExpectationDraftField,
): { ok: true; value: unknown } | { ok: false; error: string } {
  if (field.kind === 'number') {
    const value = Number(field.value)
    if (!Number.isFinite(value)) {
      return { ok: false, error: `${fieldLabel(field.key)} 必须是有效数字。` }
    }
    return { ok: true, value }
  }
  if (field.kind === 'boolean') {
    return { ok: true, value: field.value === 'true' }
  }
  if (field.kind === 'list') {
    return {
      ok: true,
      value: field.value
        .split(/[,，、]/)
        .map((item) => item.trim())
        .filter(Boolean),
    }
  }
  if (field.kind === 'json') {
    try {
      return { ok: true, value: JSON.parse(field.value) as unknown }
    } catch {
      return { ok: false, error: `${fieldLabel(field.key)} 的复杂值格式不正确。` }
    }
  }
  return { ok: true, value: field.value }
}

function inferValueKind(value: unknown): EditableValueKind {
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  if (Array.isArray(value)) return 'list'
  if (typeof value === 'object' && value !== null) return 'json'
  return 'string'
}

function draftValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).join('，')
  if (typeof value === 'object' && value !== null) return JSON.stringify(value, null, 2)
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return value === null || value === undefined ? '' : String(value)
}

function normalizeDraftKindChange(
  field: ExpectationDraftField,
  nextKind: EditableValueKind,
): ExpectationDraftPatch {
  if (nextKind === field.kind) return { kind: nextKind }
  if (nextKind === 'boolean') {
    return { kind: nextKind, value: field.value === 'false' ? 'false' : 'true' }
  }
  if (nextKind === 'number') {
    return { kind: nextKind, value: Number.isFinite(Number(field.value)) ? field.value : '' }
  }
  if (nextKind === 'json') {
    return { kind: nextKind, value: JSON.stringify(field.value, null, 2) }
  }
  return { kind: nextKind, value: field.value }
}

function formatExpectationSummary(expectation: Record<string, unknown>) {
  const entries = Object.entries(expectation)
  if (entries.length === 0) return '未设置期望字段'
  return entries.map(([key, value]) => `${fieldLabel(key)}：${formatExpectationValue(key, value)}`).join('，')
}

function formatExpectationValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '未填写'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.map((item) => formatExpectationValue(key, item)).join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  const unit = fieldUnit(key)
  return unit ? `${String(value)} ${unit}` : String(value)
}

function fieldLabel(key: string) {
  return FIELD_META[key]?.label || key
}

function fieldUnit(key: string) {
  return FIELD_META[key]?.unit
}

function categoryLabel(category: string) {
  return CATEGORY_LABELS[category] || category
}

function targetScopeLabel(scope: string) {
  return TARGET_SCOPE_LABELS[scope] || scope
}

function formatRuleTarget(rule: FormatRule) {
  return [targetScopeLabel(rule.target.scope), rule.target.selector].filter(Boolean).join(' / ')
}

function capabilityExplanation(rule: FormatRule) {
  const status = rule.capability_status || 'auto_checkable'
  if (status === 'auto_checkable') {
    return '该规则已匹配到现有检查器，启用后会自动检查并生成证据位置。'
  }
  if (status === 'needs_confirmation') {
    return rule.source.evidence_type === 'llm_candidate'
      ? '该规则来自 LLM 候选或置信度偏低，需要人工确认后再进入自动检查。'
      : '该规则字段可被系统处理，但目标范围或期望值仍需要人工确认。'
  }
  if (status === 'conflict') {
    return '系统识别到同一目标附近存在冲突表达，需要先确定最终采用哪条规则。'
  }
  if (status === 'parse_error') {
    return '系统解析这条规则时遇到错误，应回到原始规范文本定位问题后再发布。'
  }
  return '该规则当前不能进入自动检查，可导出为能力缺口并用于后续补检查器。'
}

const CATEGORY_LABELS: Record<string, string> = {
  font: '字体',
  paragraph: '段落',
  heading: '标题',
  page: '页面',
  header_footer: '页眉页脚',
  caption: '图表题注',
  reference: '参考文献',
  structure: '结构',
  toc: '目录',
  abstract: '摘要',
}

const TARGET_SCOPE_LABELS: Record<string, string> = {
  document: '全文',
  section: '章节',
  paragraph: '段落',
  'body.paragraph': '正文段落',
  heading: '标题',
  'heading.1': '一级标题',
  'heading.2': '二级标题',
  'heading.3': '三级标题',
  'heading.4': '四级标题',
  'heading.5': '五级标题',
  'heading.6': '六级标题',
  'cover.title': '论文题目',
  'abstract.paragraph': '摘要段落',
  'keywords.paragraph': '关键词段落',
  table_cell: '表格单元格',
  'table.cell': '表格单元格',
  'table.paragraph': '表格段落',
  table: '表格',
  header_footer: '页眉页脚',
  caption: '图表题注',
  reference: '参考文献',
  toc: '目录',
  abstract: '摘要',
  page: '页面',
  'document.page': '页面设置',
}

const FIELD_META: Record<string, { label: string; unit?: string }> = {
  fontFamilyEastAsia: { label: '中文字体' },
  fontFamilyAscii: { label: '英文字体' },
  fontSizePt: { label: '字号', unit: 'pt' },
  bold: { label: '加粗' },
  alignment: { label: '对齐方式' },
  firstLineIndentCm: { label: '首行缩进', unit: 'cm' },
  lineSpacing: { label: '行距' },
  spaceBeforePt: { label: '段前间距', unit: 'pt' },
  spaceAfterPt: { label: '段后间距', unit: 'pt' },
  textContains: { label: '必须包含文本' },
  requiresPageNumber: { label: '必须包含页码' },
  captionPattern: { label: '题注编号格式' },
  requiresTableCaption: { label: '表格题注' },
  requiresFigureCaption: { label: '图片题注' },
  tableCaptionPosition: { label: '表题位置' },
  figureCaptionPosition: { label: '图题位置' },
  referenceStyle: { label: '参考文献样式' },
  requiredSections: { label: '必要章节' },
  order: { label: '章节顺序' },
  autoGenerated: { label: '自动生成' },
  page_width_cm: { label: '页面宽度', unit: 'cm' },
  page_height_cm: { label: '页面高度', unit: 'cm' },
  margin_top_cm: { label: '上边距', unit: 'cm' },
  margin_bottom_cm: { label: '下边距', unit: 'cm' },
  margin_left_cm: { label: '左边距', unit: 'cm' },
  margin_right_cm: { label: '右边距', unit: 'cm' },
  header_distance_cm: { label: '页眉距边界', unit: 'cm' },
  footer_distance_cm: { label: '页脚距边界', unit: 'cm' },
}

const FIELD_OPTIONS = Object.entries(FIELD_META).map(([key, value]) => ({
  key,
  label: value.label,
}))
