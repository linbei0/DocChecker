import { cn } from '@/shared/lib/utils'

interface SeverityBadgeProps {
  severity: 'blocker' | 'major' | 'minor' | 'info'
}

const severityMap = {
  blocker: { text: '阻断', className: 'bg-danger-50 text-danger-600 border-danger-200' },
  major: { text: '严重', className: 'bg-warning-50 text-warning-600 border-warning-200' },
  minor: { text: '一般', className: 'bg-primary-50 text-primary-600 border-primary-200' },
  info: { text: '提示', className: 'bg-neutral-100 text-neutral-600 border-neutral-200' },
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const config = severityMap[severity]
  return (
    <span className={cn('inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium', config.className)}>
      {config.text}
    </span>
  )
}
