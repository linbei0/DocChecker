import { Link } from 'react-router'
import { ClipboardList, FileText, Plus, RefreshCw } from 'lucide-react'
import { useRuleSetsQuery } from '@/features/rulesets/hooks'
import { StatusBadge } from '@/shared/ui/StatusBadge'
import { Button } from '@/shared/ui/Button'

export function TemplatesPage() {
  const { data: ruleSets = [], isLoading, isError, refetch } = useRuleSetsQuery()

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-lg font-semibold text-neutral-900">规则模板</h1>
          <p className="mt-1 text-sm text-neutral-500">
            管理论文格式规则集，后续可从手动输入或格式规范文件发布为模板。
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

      <section className="rounded-xl border border-neutral-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-neutral-200 px-5 py-4">
          <div>
            <h2 className="text-sm font-medium text-neutral-900">已发布规则集</h2>
            <p className="mt-1 text-xs text-neutral-500">共 {ruleSets.length} 个模板</p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => void refetch()} disabled={isLoading}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            刷新
          </Button>
        </div>

        {isLoading ? (
          <div className="px-5 py-12 text-center text-sm text-neutral-500">正在加载规则模板...</div>
        ) : isError ? (
          <div className="px-5 py-12 text-center">
            <p className="text-sm text-danger-600">规则模板加载失败，请确认后端服务和 API 代理配置。</p>
          </div>
        ) : ruleSets.length === 0 ? (
          <div className="px-5 py-16 text-center">
            <ClipboardList className="mx-auto h-10 w-10 text-neutral-300" />
            <h3 className="mt-4 text-sm font-medium text-neutral-900">暂无规则模板</h3>
            <p className="mt-2 text-sm text-neutral-500">
              先从新建检查流程创建规则集，确认后即可在这里复用。
            </p>
            <Link
              to="/checks/new"
              className="mt-5 inline-flex h-10 items-center justify-center rounded-lg bg-primary-600 px-4 text-sm font-medium text-white transition-colors hover:bg-primary-700"
            >
              去新建检查
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-neutral-50">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                    模板名称
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                    来源
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                    版本
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                    规则数
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                    创建时间
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200">
                {ruleSets.map((ruleSet) => (
                  <tr key={ruleSet.id} className="hover:bg-neutral-50">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-50 text-primary-700">
                          <FileText className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="font-medium text-neutral-900">{ruleSet.name}</div>
                          <div className="text-xs text-neutral-400">{ruleSet.id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-neutral-700">{sourceText[ruleSet.source_type]}</td>
                    <td className="px-5 py-4 text-neutral-700">{ruleSet.version}</td>
                    <td className="px-5 py-4">
                      <StatusBadge status="enabled" text={`${ruleSet.rules.length} 条`} />
                    </td>
                    <td className="px-5 py-4 text-neutral-500">
                      {new Date(ruleSet.created_at).toLocaleString()}
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

const sourceText = {
  manual: '手动输入',
  requirement_doc: '格式规范文档',
  template: '模板复制',
}
