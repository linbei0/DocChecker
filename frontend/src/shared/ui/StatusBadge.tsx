import { cn } from '@/shared/lib/utils'

interface StatusBadgeProps {
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'enabled' | 'disabled' | 'conflict'
  text?: string
}

const statusMap = {
  pending: { text: '待处理', className: 'bg-neutral-100 text-neutral-600' },
  running: { text: '进行中', className: 'bg-primary-100 text-primary-700' },
  succeeded: { text: '成功', className: 'bg-success-50 text-success-600' },
  failed: { text: '失败', className: 'bg-danger-50 text-danger-600' },
  enabled: { text: '启用', className: 'bg-success-50 text-success-600' },
  disabled: { text: '禁用', className: 'bg-neutral-100 text-neutral-600' },
  conflict: { text: '冲突', className: 'bg-danger-50 text-danger-600' },
}

export function StatusBadge({ status, text }: StatusBadgeProps) {
  const config = statusMap[status]
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', config.className)}>
      {text || config.text}
    </span>
  )
}
