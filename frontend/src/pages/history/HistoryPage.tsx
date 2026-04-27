import { Link } from 'react-router'
import { FileText, History, Plus } from 'lucide-react'
import { useCheckTasksQuery } from '@/features/check-tasks/hooks'
import { StatusBadge } from '@/shared/ui/StatusBadge'

export function HistoryPage() {
  const { data: tasks = [], isLoading, isError } = useCheckTasksQuery()

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-lg font-semibold text-neutral-900">历史任务</h1>
          <p className="mt-1 text-sm text-neutral-500">查看本次服务运行期间创建的检查任务。</p>
        </div>
        <Link
          to="/checks/new"
          className="inline-flex h-10 items-center justify-center rounded-lg bg-primary-600 px-4 text-sm font-medium text-white transition-colors hover:bg-primary-700"
        >
          <Plus className="mr-1.5 h-4 w-4" />
          新建检查
        </Link>
      </div>

      <section className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
        {isLoading ? (
          <div className="px-5 py-12 text-center text-sm text-neutral-500">加载历史任务中...</div>
        ) : isError ? (
          <div className="px-5 py-12 text-center text-sm text-danger-600">历史任务加载失败。</div>
        ) : tasks.length === 0 ? (
          <div className="px-5 py-16 text-center">
            <History className="mx-auto h-10 w-10 text-neutral-300" />
            <h2 className="mt-4 text-sm font-medium text-neutral-900">暂无历史任务</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-neutral-500">
              完成一次检查后，任务状态和报告入口会显示在这里。
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-neutral-50">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                    任务
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                    状态
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                    规则集
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                    更新时间
                  </th>
                  <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wider text-neutral-500">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200">
                {tasks.map((task) => (
                  <tr key={task.id} className="hover:bg-neutral-50">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-50 text-primary-700">
                          <FileText className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="font-medium text-neutral-900">{task.id}</div>
                          <div className="text-xs text-neutral-400">{task.document_id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <StatusBadge status={task.status} />
                    </td>
                    <td className="px-5 py-4 text-neutral-700">{task.ruleset_id}</td>
                    <td className="px-5 py-4 text-neutral-500">
                      {new Date(task.updated_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-4 text-right">
                      {task.report_id ? (
                        <Link to={`/reports/${task.report_id}`} className="text-primary-600 hover:underline">
                          查看报告
                        </Link>
                      ) : (
                        <Link to={`/checks/${task.id}/progress`} className="text-primary-600 hover:underline">
                          查看进度
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
