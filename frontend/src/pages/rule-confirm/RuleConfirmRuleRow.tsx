import { AlertCircle, ChevronDown, Edit2, PlusCircle } from 'lucide-react'
import type { FormatRule } from '@/entities/ruleset/model'
import { SeverityBadge } from '@/shared/ui/SeverityBadge'
import { Button } from '@/shared/ui/Button'
import { cn } from '@/shared/lib/utils'
import type { ExpectationDraftField, ExpectationDraftPatch } from './ruleConfirmText'
import { ExpectationEditor } from './RuleExpectationEditor'
import {
  capabilityExplanation,
  capabilityStatusLabel,
  categoryLabel,
  evidenceTypeLabel,
  fieldLabel,
  formatExpectationSummary,
  formatExpectationValue,
  formatRuleTarget,
} from './ruleConfirmText'

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


export function RuleRow({
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
