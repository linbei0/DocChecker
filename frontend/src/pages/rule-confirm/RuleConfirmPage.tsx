import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  Edit2,
  Eye,
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

type ReviewFilter = 'all' | 'auto' | 'confirmation' | 'unsupported'

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
            nextEnabled && rule.capability_status === 'needs_confirmation'
              ? 'auto_checkable'
              : rule.capability_status,
          confirmation_required:
            nextEnabled && rule.capability_status === 'needs_confirmation'
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
                enabled && rule.capability_status === 'needs_confirmation'
                  ? 'auto_checkable'
                  : rule.capability_status,
              confirmation_required:
                enabled && rule.capability_status === 'needs_confirmation'
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
      const autoRules = rules.filter((rule) => rule.capability_status !== 'needs_confirmation')
      const suggestedRules = rules.filter(
        (rule) => rule.capability_status === 'needs_confirmation',
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

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 text-sm text-neutral-500">
        加载候选规则中...
      </div>
    )
  }

  if (!draft) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 text-center">
        <AlertCircle className="mx-auto h-10 w-10 text-neutral-300" />
        <p className="mt-4 text-sm text-neutral-600">候选规则集不存在或已过期。</p>
        <Link
          to="/checks/new"
          className="mt-4 inline-block text-sm text-primary-600 hover:underline"
        >
          返回新建检查
        </Link>
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
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-neutral-900">确认规则</h1>
          <p className="mt-1 text-sm text-neutral-500">
            所有规则诊断、人工确认和不可校验说明都在同一工作台里完成。
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => navigate(-1)}>
            <ArrowLeft className="mr-1 h-4 w-4" />
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
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-danger-50 bg-danger-50 p-3 text-sm text-danger-600">
          {error}
        </div>
      )}

      {draft.parse_warnings.length > 0 && (
        <div className="mb-4 rounded-lg border border-warning-50 bg-warning-50 p-3 text-sm text-warning-700">
          {draft.parse_warnings.join('；')}
        </div>
      )}

      {summary && (
        <div className="mb-4 grid gap-3 sm:grid-cols-4">
          <SummaryMetric label="识别到要求" value={summary.total_requirements} />
          <SummaryMetric label="可自动校验" value={summary.structured_rules} tone="success" />
          <SummaryMetric
            label="需人工确认"
            value={summary.needs_confirmation_rules ?? summary.low_confidence_rules}
            tone="warning"
          />
          <SummaryMetric label="当前不可校验" value={summary.unsupported_requirements} tone="danger" />
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
        <div className="border-b border-neutral-200 px-6 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-medium text-neutral-900">规则诊断与确认工作台</h2>
              <p className="mt-1 text-xs text-neutral-500">
                在同一列表里处理自动规则、人工确认项和当前不可校验项。
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRulesEnabled(true, (rule) => visibleRules.includes(rule))}
                disabled={visibleRules.length === 0}
              >
                <CheckCircle className="mr-1 h-4 w-4" />
                启用当前筛选
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRulesEnabled(false, (rule) => visibleRules.includes(rule))}
                disabled={visibleRules.length === 0}
              >
                <XCircle className="mr-1 h-4 w-4" />
                禁用当前筛选
              </Button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {FILTER_OPTIONS.map((option) => (
              <button
                key={option.id}
                onClick={() => setActiveFilter(option.id)}
                className={cn(
                  'rounded-full border px-3 py-1.5 text-xs transition-colors',
                  activeFilter === option.id
                    ? 'border-primary-600 bg-primary-50 text-primary-700'
                    : 'border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50',
                )}
              >
                {option.label}
                <span className="ml-1 text-neutral-400">{countByFilter(reviewItems, option.id)}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                  状态
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                  类别
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                  能力状态
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                  适用范围
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                  内容
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                  严重度
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-neutral-500">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200">
              {visibleItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-neutral-400">
                    当前筛选下没有项目。
                  </td>
                </tr>
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
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

const FILTER_OPTIONS: Array<{ id: ReviewFilter; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'auto', label: '可自动校验' },
  { id: 'confirmation', label: '建议人工确认' },
  { id: 'unsupported', label: '当前不可校验' },
]

function buildReviewItems(
  rules: FormatRule[],
  unsupportedRequirements: UnsupportedRequirement[],
): ReviewItem[] {
  const ruleItems: ReviewItem[] = rules.map((rule) => ({
    id: `rule:${rule.id}`,
    kind: 'rule',
    title: rule.target.selector || rule.target.scope,
    rule,
  }))
  const unsupportedItems: ReviewItem[] = unsupportedRequirements.map((requirement, index) => ({
    id: `unsupported:${requirement.location || index}:${requirement.excerpt}`,
    kind: 'unsupported',
    title: requirement.target_scope || requirement.location || requirement.category,
    requirement,
  }))
  return [...ruleItems, ...unsupportedItems]
}

function matchesFilter(item: ReviewItem, filter: ReviewFilter): boolean {
  if (filter === 'all') return true
  if (item.kind === 'unsupported') return filter === 'unsupported'
  if (filter === 'auto') return item.rule.capability_status !== 'needs_confirmation'
  if (filter === 'confirmation') return item.rule.capability_status === 'needs_confirmation'
  return false
}

function countByFilter(items: ReviewItem[], filter: ReviewFilter): number {
  return items.filter((item) => matchesFilter(item, filter)).length
}

function SummaryMetric({
  label,
  value,
  tone = 'neutral',
}: {
  label: string
  value: number
  tone?: 'neutral' | 'success' | 'warning' | 'danger'
}) {
  const toneClass = {
    neutral: 'text-neutral-900',
    success: 'text-success-600',
    warning: 'text-warning-700',
    danger: 'text-danger-600',
  }[tone]

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
      <p className="text-xs text-neutral-500">{label}</p>
      <p className={cn('mt-1 text-2xl font-semibold', toneClass)}>{value}</p>
    </div>
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
  return (
    <>
      <tr className="transition-colors hover:bg-neutral-50">
        <td className="px-6 py-4">
          <span className="rounded-full bg-neutral-100 px-2 py-1 text-xs text-neutral-500">
            不可启用
          </span>
        </td>
        <td className="px-6 py-4 text-neutral-900">{requirement.category}</td>
        <td className="px-6 py-4">
          <span className="rounded-full bg-warning-50 px-2 py-0.5 text-xs text-warning-700">
            {capabilityStatusLabel(requirement.capability_status || 'unsupported')}
          </span>
        </td>
        <td className="px-6 py-4 text-neutral-700">
          {requirement.target_scope || requirement.location || '未定位'}
        </td>
        <td className="px-6 py-4 text-neutral-700">{requirement.excerpt}</td>
        <td className="px-6 py-4">
          <span className="rounded-full border border-neutral-200 px-2 py-0.5 text-xs text-neutral-500">
            说明
          </span>
        </td>
        <td className="px-6 py-4 text-right">
          <button
            onClick={onExpand}
            className="rounded-md p-1 text-neutral-400 hover:bg-neutral-200"
          >
            <Eye className="h-4 w-4" />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} className="border-t border-neutral-100 bg-neutral-50 px-6 py-4">
            <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
              <div>
                <p className="text-xs text-neutral-500">原始要求</p>
                <p className="mt-2 rounded-lg border border-neutral-200 bg-white p-3 text-sm text-neutral-700">
                  {requirement.excerpt}
                </p>
                <p className="mt-2 text-xs text-neutral-500">
                  来源位置：{requirement.location || '未定位'}
                </p>
                {requirement.reason_code && (
                  <p className="mt-2 text-xs text-neutral-500">
                    诊断类型：{reasonCodeLabel(requirement.reason_code)}
                  </p>
                )}
              </div>
              <div>
                <p className="text-xs text-neutral-500">当前状态说明</p>
                <div className="mt-2 rounded-lg border border-warning-100 bg-white p-3 text-sm text-neutral-700">
                  <p>{requirement.reason}</p>
                  <p className="mt-2 text-xs text-warning-700">
                    {unsupportedActionHint(requirement)}
                  </p>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
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
  return (
    <>
      <tr className={cn('transition-colors hover:bg-neutral-50', rule.enabled === false && 'opacity-60')}>
        <td className="px-6 py-4">
          <button
            onClick={onToggle}
            className={cn(
              'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
              rule.enabled !== false ? 'bg-primary-600' : 'bg-neutral-300',
            )}
          >
            <span
              className={cn(
                'inline-block h-3 w-3 transform rounded-full bg-white transition-transform',
                rule.enabled !== false ? 'translate-x-5' : 'translate-x-1',
              )}
            />
          </button>
        </td>
        <td className="px-6 py-4 text-neutral-900">{rule.category}</td>
        <td className="px-6 py-4">
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs',
              rule.capability_status === 'needs_confirmation'
                ? 'bg-warning-50 text-warning-700'
                : 'bg-success-50 text-success-700',
            )}
          >
            {capabilityStatusLabel(rule.capability_status || 'auto_checkable')}
          </span>
        </td>
        <td className="px-6 py-4 text-neutral-700">{rule.target.selector || rule.target.scope}</td>
        <td className="px-6 py-4 text-neutral-700">
          {Object.entries(rule.expectation)
            .map(([key, value]) => `${key}: ${String(value)}`)
            .join(', ')}
        </td>
        <td className="px-6 py-4">
          <SeverityBadge severity={rule.severity} />
        </td>
        <td className="px-6 py-4 text-right">
          <button
            onClick={onExpand}
            className="rounded-md p-1 text-neutral-400 hover:bg-neutral-200"
          >
            <Edit2 className="h-4 w-4" />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} className="border-t border-neutral-100 bg-neutral-50 px-6 py-4">
            <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
              <div>
                <p className="text-xs text-neutral-500">来源片段</p>
                <p className="mt-2 rounded-lg border border-neutral-200 bg-white p-3 text-sm text-neutral-700">
                  {rule.source.excerpt || '无来源片段'}
                </p>
                <p className="mt-2 text-xs text-neutral-500">
                  来源位置：{rule.source.location || '未定位'} · 置信度：
                  {Math.round((rule.confidence ?? 1) * 100)}%
                  {' · '}证据类型：{evidenceTypeLabel(rule.source.evidence_type || 'explicit_text')}
                </p>
                {rule.capability_status === 'needs_confirmation' && (
                  <p className="mt-2 rounded-lg bg-warning-50 px-3 py-2 text-xs text-warning-700">
                    这条规则需要你人工确认后再启用。编辑期望值并打开左侧开关后，它才会参与正式检查。
                  </p>
                )}
              </div>
              <div className="space-y-3">
                <label className="block">
                  <span className="text-xs text-neutral-500">严重度</span>
                  <select
                    value={rule.severity}
                    onChange={(event) =>
                      onSeverityChange(event.target.value as FormatRule['severity'])
                    }
                    className="mt-2 block w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
                  >
                    <option value="blocker">阻断</option>
                    <option value="major">严重</option>
                    <option value="minor">一般</option>
                    <option value="info">提示</option>
                  </select>
                </label>
                {editing ? (
                  <div>
                    <span className="text-xs text-neutral-500">期望值 JSON</span>
                    <textarea
                      value={expectationText}
                      onChange={(event) => onExpectationTextChange(event.target.value)}
                      rows={5}
                      className="mt-2 w-full rounded-lg border border-neutral-200 bg-white p-3 font-mono text-xs"
                    />
                    <div className="mt-2 flex gap-2">
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
                    编辑期望值
                  </Button>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
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
    return '这类项通常对应同目标的冲突规则。请优先在“建议人工确认”筛选里确认最终可执行规则。'
  }
  if (requirement.capability_status === 'needs_confirmation') {
    return '这类项本身还没有形成可执行规则，不能直接启用，需要先补充更明确的规则表达。'
  }
  return '这类项当前没有对应检查器，暂时不能直接人工确认成自动检查规则。'
}
