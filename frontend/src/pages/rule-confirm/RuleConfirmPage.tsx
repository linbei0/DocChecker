import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle, Edit2, XCircle } from 'lucide-react'
import { Button } from '@/shared/ui/Button'
import { SeverityBadge } from '@/shared/ui/SeverityBadge'
import { cn } from '@/shared/lib/utils'
import type { FormatRule } from '@/entities/ruleset/model'
import {
  useDraftRuleSetQuery,
  usePublishDraftRuleSetMutation,
  useUpdateDraftRuleSetMutation,
} from '@/features/rulesets/hooks'
import { useCreateCheckTaskMutation } from '@/features/check-tasks/hooks'

export function RuleConfirmPage() {
  const { taskId: draftId = '' } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const { data: draft, isLoading } = useDraftRuleSetQuery(draftId)
  const updateDraftMutation = useUpdateDraftRuleSetMutation(draftId)
  const publishDraftMutation = usePublishDraftRuleSetMutation()
  const createCheckTaskMutation = useCreateCheckTaskMutation()
  const [rules, setRules] = useState<FormatRule[]>([])
  const [expandedRule, setExpandedRule] = useState<string | null>(null)
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null)
  const [expectationText, setExpectationText] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (draft) setRules(draft.rules)
  }, [draft])

  const toggleRule = (id: string) => {
    setRules((prev) => prev.map((rule) => (rule.id === id ? { ...rule, enabled: !rule.enabled } : rule)))
  }

  const setAllRulesEnabled = (enabled: boolean) => {
    setRules((prev) => prev.map((rule) => ({ ...rule, enabled })))
  }

  const startEditing = (rule: FormatRule) => {
    setEditingRuleId(rule.id)
    setExpandedRule(rule.id)
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
      await updateDraftMutation.mutateAsync({ rules, name: draft.name })
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
    return <div className="mx-auto max-w-7xl px-4 py-12 text-sm text-neutral-500">加载候选规则中...</div>
  }

  if (!draft) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 text-center">
        <AlertCircle className="mx-auto h-10 w-10 text-neutral-300" />
        <p className="mt-4 text-sm text-neutral-600">候选规则集不存在或已过期。</p>
        <Link to="/checks/new" className="mt-4 inline-block text-sm text-primary-600 hover:underline">
          返回新建检查
        </Link>
      </div>
    )
  }

  const enabledCount = rules.filter((rule) => rule.enabled !== false).length
  const summary = draft.extraction_summary
  const unsupportedRequirements = draft.unsupported_requirements ?? []
  const lowConfidenceRules = rules.filter((rule) => (rule.confidence ?? 1) < 0.8)

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-neutral-900">确认规则</h1>
          <p className="mt-1 text-sm text-neutral-500">系统已从所选来源中提取规则，请确认或调整。</p>
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
        <div className="mb-4 rounded-lg border border-warning-50 bg-warning-50 p-3 text-sm text-warning-600">
          {draft.parse_warnings.join('；')}
        </div>
      )}

      {summary && (
        <div className="mb-4 grid gap-3 sm:grid-cols-4">
          <SummaryMetric label="识别到要求" value={summary.total_requirements} />
          <SummaryMetric label="可自动校验" value={summary.structured_rules} tone="success" />
          <SummaryMetric label="需人工确认" value={summary.low_confidence_rules} tone="warning" />
          <SummaryMetric label="当前不可校验" value={summary.unsupported_requirements} tone="danger" />
        </div>
      )}

      {unsupportedRequirements.length > 0 && (
        <div className="mb-4 rounded-xl border border-warning-100 bg-warning-50 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-warning-700">
            <AlertCircle className="h-4 w-4" />
            当前不可自动校验的要求
          </div>
          <div className="mt-3 space-y-2">
            {unsupportedRequirements.map((item, index) => (
              <div key={`${item.category}-${item.location || index}`} className="rounded-lg bg-white p-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
                  <span className="font-medium text-neutral-700">{item.category}</span>
                  {item.location && <span>{item.location}</span>}
                  {item.reason_code && (
                    <span className="rounded-full bg-warning-50 px-2 py-0.5 text-warning-700">
                      {reasonCodeLabel(item.reason_code)}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-sm text-neutral-700">{item.excerpt}</p>
                <p className="mt-1 text-xs text-warning-700">{item.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-neutral-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-neutral-900">可自动校验规则</span>
            <span className="text-xs text-neutral-500">
              ({enabledCount}/{rules.length} 条已启用)
            </span>
            {lowConfidenceRules.length > 0 && (
              <span className="rounded-full bg-warning-50 px-2 py-0.5 text-xs text-warning-700">
                {lowConfidenceRules.length} 条需核对
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setAllRulesEnabled(true)}>
              <CheckCircle className="mr-1 h-4 w-4" />
              全部启用
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setAllRulesEnabled(false)}>
              <XCircle className="mr-1 h-4 w-4" />
              全部禁用
            </Button>
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
                  适用范围
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                  期望值
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
              {rules.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-neutral-400">
                    未生成候选规则，请返回上一步补充更明确的格式要求。
                  </td>
                </tr>
              ) : (
                rules.map((rule) => (
                  <RuleRow
                    key={rule.id}
                    rule={rule}
                    expanded={expandedRule === rule.id}
                    editing={editingRuleId === rule.id}
                    expectationText={expectationText}
                    onExpectationTextChange={setExpectationText}
                    onToggle={() => toggleRule(rule.id)}
                    onExpand={() => setExpandedRule(expandedRule === rule.id ? null : rule.id)}
                    onEdit={() => startEditing(rule)}
                    onCancelEdit={() => setEditingRuleId(null)}
                    onSaveEdit={() => saveRuleEdit(rule.id)}
                    onSeverityChange={(severity) =>
                      setRules((prev) =>
                        prev.map((item) => (item.id === rule.id ? { ...item, severity } : item)),
                      )
                    }
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
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

function reasonCodeLabel(code: string) {
  return (
    {
      missing_checker: '缺少检查器',
      ambiguous_requirement: '语义不明确',
      out_of_scope: '超出范围',
      llm_not_configured: 'LLM 未配置',
      invalid_llm_response: 'LLM 响应无效',
    }[code] || code
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
          <button onClick={onExpand} className="rounded-md p-1 text-neutral-400 hover:bg-neutral-200">
            <Edit2 className="h-4 w-4" />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6} className="border-t border-neutral-100 bg-neutral-50 px-6 py-4">
            <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
              <div>
                <p className="text-xs text-neutral-500">来源片段</p>
                <p className="mt-2 rounded-lg border border-neutral-200 bg-white p-3 text-sm text-neutral-700">
                  {rule.source.excerpt || '无来源片段'}
                </p>
                <p className="mt-2 text-xs text-neutral-500">
                  来源位置：{rule.source.location || '未定位'} · 置信度：
                  {Math.round((rule.confidence ?? 1) * 100)}%
                </p>
              </div>
              <div className="space-y-3">
                <label className="block">
                  <span className="text-xs text-neutral-500">严重度</span>
                  <select
                    value={rule.severity}
                    onChange={(event) => onSeverityChange(event.target.value as FormatRule['severity'])}
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
