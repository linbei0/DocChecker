import { Link, useParams } from 'react-router'
import { AlertCircle, CheckCircle, Clock, FileText } from 'lucide-react'
import { useCheckTaskQuery } from '@/features/check-tasks/hooks'
import { Button } from '@/shared/ui/Button'
import { StatusBadge } from '@/shared/ui/StatusBadge'

export function CheckProgressPage() {
  const { taskId = '' } = useParams<{ taskId: string }>()
  const { data: task, isLoading } = useCheckTaskQuery(taskId)

  if (isLoading) {
    return <div className="mx-auto max-w-4xl px-4 py-12 text-sm text-neutral-500">加载检查任务中...</div>
  }

  if (!task) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12 text-center">
        <AlertCircle className="mx-auto h-10 w-10 text-neutral-300" />
        <p className="mt-4 text-sm text-neutral-600">检查任务不存在或已过期。</p>
        <Link to="/checks/new" className="mt-4 inline-block text-sm text-primary-600 hover:underline">
          返回新建检查
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="rounded-xl border border-neutral-200 bg-white p-8 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-50 text-primary-700">
            {task.status === 'succeeded' ? (
              <CheckCircle className="h-6 w-6" />
            ) : task.status === 'failed' ? (
              <AlertCircle className="h-6 w-6 text-danger-600" />
            ) : (
              <Clock className="h-6 w-6 animate-spin" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold text-neutral-900">检查进度</h1>
              <StatusBadge status={task.status} />
            </div>
            <p className="mt-2 text-sm text-neutral-500">
              MVP 当前同步执行检查，页面保留任务状态轮询，后续可平滑切换到 RQ worker。
            </p>
          </div>
        </div>

        <div className="mt-8 grid gap-3">
          {progressSteps.map((step, index) => (
            <div key={step} className="flex items-center gap-3 rounded-lg border border-neutral-200 p-3">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-success-50 text-success-600">
                <CheckCircle className="h-4 w-4" />
              </div>
              <span className="text-sm text-neutral-700">{index + 1}. {step}</span>
            </div>
          ))}
        </div>

        {task.error && (
          <div className="mt-6 rounded-lg border border-danger-50 bg-danger-50 p-3 text-sm text-danger-600">
            {task.error}
          </div>
        )}

        <div className="mt-8 flex items-center justify-between border-t border-neutral-200 pt-5">
          <div className="flex items-center gap-2 text-sm text-neutral-500">
            <FileText className="h-4 w-4" />
            <span>{task.id}</span>
          </div>
          {task.status === 'succeeded' && task.report_id ? (
            <Link to={`/reports/${task.report_id}`}>
              <Button>查看报告</Button>
            </Link>
          ) : task.status === 'failed' ? (
            <Link to="/checks/new">
              <Button variant="secondary">重新创建检查</Button>
            </Link>
          ) : (
            <Button disabled isLoading>
              检查中
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

const progressSteps = ['上传校验', 'DOCX 包解析', '样式与段落建模', '执行检查器', '生成报告']
