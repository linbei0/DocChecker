import { Fragment, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  Download,
  XCircle,
} from 'lucide-react'
import { Button } from '@/shared/ui/Button'
import type { FormatRule } from '@/entities/ruleset/model'
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
} from './ruleReviewDiagnostics'
import {
  FILTER_OPTIONS,
  buildReviewGroups,
  buildReviewItems,
  countByFilter,
  matchesFilter,
type ReviewFilter,
  type RuleReviewItem,
} from './ruleConfirmModel'
import { createExpectationDraft, serializeExpectationDraft, type ExpectationDraftField, type ExpectationDraftPatch } from './ruleConfirmText'
import { FeedbackGroupCard, FilterPill, RuleGroupHeader, SummaryMetric, TraceMetric } from './RuleConfirmMetrics'
import { RuleRow } from './RuleConfirmRuleRow'
import { UnsupportedRow } from './RuleConfirmUnsupportedRow'
import {
  RuleConfirmFailed,
  RuleConfirmLoading,
  RuleConfirmMissing,
  RuleConfirmProcessing,
} from './RuleConfirmStates'

interface TemplateMetadataDraft {
  name: string
  school: string
  college: string
  thesisType: string
  versionNote: string
}

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
  const [templateMetadata, setTemplateMetadata] = useState<TemplateMetadataDraft>({
    name: '',
    school: '',
    college: '',
    thesisType: '',
    versionNote: '',
  })

  useEffect(() => {
    if (draft) {
      setRules([...draft.rules, ...(draft.suggested_rules ?? [])])
      setTemplateMetadata({
        name: draft.name,
        school: draft.school ?? '',
        college: draft.college ?? '',
        thesisType: draft.thesis_type ?? '',
        versionNote: draft.version_note ?? '',
      })
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
        name: templateMetadata.name.trim() || draft.name,
        school: cleanTemplateMetadata(templateMetadata.school),
        college: cleanTemplateMetadata(templateMetadata.college),
        thesis_type: cleanTemplateMetadata(templateMetadata.thesisType),
        version_note: cleanTemplateMetadata(templateMetadata.versionNote),
      })
      const ruleset = await publishDraftMutation.mutateAsync({
        draftId: draft.id,
        request: {
          name: templateMetadata.name.trim() || draft.name,
          school: cleanTemplateMetadata(templateMetadata.school),
          college: cleanTemplateMetadata(templateMetadata.college),
          thesis_type: cleanTemplateMetadata(templateMetadata.thesisType),
          version_note: cleanTemplateMetadata(templateMetadata.versionNote),
        },
      })
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

  if (isLoading) return <RuleConfirmLoading />

  if (!draft) return <RuleConfirmMissing />

  if (draft.status === 'processing') {
    return (
      <RuleConfirmProcessing
        message={draft.parse_warnings[0] || '规则抽取正在后台执行。'}
        onBack={() => navigate('/checks/new')}
      />
    )
  }

  if (draft.status === 'failed') {
    return (
      <RuleConfirmFailed
        message={draft.error || '未知错误'}
        onBack={() => navigate('/checks/new')}
      />
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

      <section className="mb-6 rounded-xl border border-neutral-200 bg-white px-5 py-5 shadow-sm">
        <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-neutral-900">模板信息</h2>
            <p className="mt-1 text-xs text-neutral-500">
              发布后会作为个人模板保存，后续检查可直接复用。
            </p>
          </div>
          <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-600">
            v{draft.version}
          </span>
        </div>
        <div className="grid gap-3 lg:grid-cols-[1.2fr_1fr_1fr_1fr]">
          <TemplateTextField
            label="模板名称"
            value={templateMetadata.name}
            onChange={(name) => setTemplateMetadata((prev) => ({ ...prev, name }))}
            placeholder="学校论文格式模板"
          />
          <TemplateTextField
            label="学校"
            value={templateMetadata.school}
            onChange={(school) => setTemplateMetadata((prev) => ({ ...prev, school }))}
            placeholder="未填写"
          />
          <TemplateTextField
            label="学院"
            value={templateMetadata.college}
            onChange={(college) => setTemplateMetadata((prev) => ({ ...prev, college }))}
            placeholder="未填写"
          />
          <TemplateTextField
            label="论文类型"
            value={templateMetadata.thesisType}
            onChange={(thesisType) => setTemplateMetadata((prev) => ({ ...prev, thesisType }))}
            placeholder="本科 / 硕士 / 博士"
          />
        </div>
        <div className="mt-3">
          <TemplateTextField
            label="版本备注"
            value={templateMetadata.versionNote}
            onChange={(versionNote) => setTemplateMetadata((prev) => ({ ...prev, versionNote }))}
            placeholder="例如：2026 届论文格式规范"
          />
        </div>
      </section>

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

function TemplateTextField({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string
  value: string
  placeholder: string
  onChange: (value: string) => void
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-neutral-500">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="mt-1 h-10 w-full rounded-lg border border-neutral-300 px-3 text-sm text-neutral-900 outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
      />
    </label>
  )
}

function cleanTemplateMetadata(value: string) {
  const trimmed = value.trim()
  return trimmed || null
}
