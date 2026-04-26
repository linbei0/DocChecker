import { Link } from 'react-router'
import { History, Plus } from 'lucide-react'

export function HistoryPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-lg font-semibold text-neutral-900">历史任务</h1>
          <p className="mt-1 text-sm text-neutral-500">
            后端持久化任务列表完成后，这里会展示检查时间、规则集、问题数量和报告入口。
          </p>
        </div>
        <Link
          to="/checks/new"
          className="inline-flex h-10 items-center justify-center rounded-lg bg-primary-600 px-4 text-sm font-medium text-white transition-colors hover:bg-primary-700"
        >
          <Plus className="mr-1.5 h-4 w-4" />
          新建检查
        </Link>
      </div>

      <section className="rounded-xl border border-neutral-200 bg-white px-5 py-16 text-center shadow-sm">
        <History className="mx-auto h-10 w-10 text-neutral-300" />
        <h2 className="mt-4 text-sm font-medium text-neutral-900">暂无可查询的历史任务</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-neutral-500">
          当前后端只保留运行期内存中的报告详情，尚未提供历史任务列表接口。页面先占位，避免导航进入未注册路由。
        </p>
        <Link
          to="/checks/new"
          className="mt-5 inline-flex h-10 items-center justify-center rounded-lg border border-neutral-200 bg-white px-4 text-sm font-medium text-neutral-800 transition-colors hover:bg-neutral-50"
        >
          返回新建检查
        </Link>
      </section>
    </div>
  )
}
