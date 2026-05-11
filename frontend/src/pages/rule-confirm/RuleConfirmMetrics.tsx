import type { ReactNode } from 'react'
import type { FeedbackGroup } from './ruleReviewDiagnostics'
import { cn } from '@/shared/lib/utils'
import type { ReviewGroup } from './ruleConfirmModel'
import { categoryLabel } from './ruleConfirmText'

export function SummaryMetric({
  label,
  value,
  tone = 'neutral',
  icon,
}: {
  label: string
  value: number
  tone?: 'neutral' | 'success' | 'warning' | 'danger'
  icon?: ReactNode
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

export function TraceMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-neutral-100 bg-neutral-50/70 px-3.5 py-3">
      <p className="text-[11px] font-medium text-neutral-500">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-neutral-900">{value}</p>
    </div>
  )
}

export function FeedbackGroupCard({
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

export function RuleGroupHeader({ group }: { group: ReviewGroup }) {
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

export function FilterPill({
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

