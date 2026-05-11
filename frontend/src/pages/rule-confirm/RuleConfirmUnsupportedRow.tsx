import { useRef } from 'react'
import { ChevronDown } from 'lucide-react'
import type { UnsupportedRequirement } from '@/entities/ruleset/model'
import { cn } from '@/shared/lib/utils'
import {
  capabilityStatusLabel,
  reasonCodeLabel,
  unsupportedActionHint,
} from './ruleConfirmText'

export function UnsupportedRow({
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
