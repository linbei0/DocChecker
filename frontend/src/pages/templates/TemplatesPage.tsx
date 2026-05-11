import { useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { ClipboardList, Plus, RefreshCw } from 'lucide-react'
import {
  useDeleteRuleSetMutation,
  useRuleSetsQuery,
  useUpdateRuleSetMutation,
} from '@/features/rulesets/hooks'
import { type RuleSet } from '@/entities/ruleset/model'
import { Button } from '@/shared/ui/Button'
import { RuleDetails, TemplateCard, TemplateRows } from './TemplateList'

const PAGE_SIZE = 20

export function TemplatesPage() {
  const [offset, setOffset] = useState(0)
  const { data: ruleSets = [], isLoading, isError, refetch } = useRuleSetsQuery({
    limit: PAGE_SIZE,
    offset,
  })
  const [expandedRuleSetId, setExpandedRuleSetId] = useState<string | null>(null)
  const [editingRuleSetId, setEditingRuleSetId] = useState<string | null>(null)
  const [deletingRuleSetId, setDeletingRuleSetId] = useState<string | null>(null)
  const [draftName, setDraftName] = useState('')
  const updateRuleSetMutation = useUpdateRuleSetMutation(editingRuleSetId || '')
  const deleteRuleSetMutation = useDeleteRuleSetMutation()
  const page = Math.floor(offset / PAGE_SIZE) + 1

  const expandedRuleSet = useMemo(
    () => ruleSets.find((ruleSet) => ruleSet.id === expandedRuleSetId) || null,
    [expandedRuleSetId, ruleSets],
  )

  const startEditing = (ruleSet: RuleSet) => {
    setEditingRuleSetId(ruleSet.id)
    setDraftName(ruleSet.name)
  }

  const cancelEditing = () => {
    setEditingRuleSetId(null)
    setDraftName('')
  }

  const submitRename = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const name = draftName.trim()
    if (!editingRuleSetId || !name) return
    updateRuleSetMutation.mutate(
      { name },
      {
        onSuccess: () => {
          cancelEditing()
        },
      },
    )
  }

  const deleteRuleSet = (ruleSet: RuleSet) => {
    const confirmed = window.confirm(`确定删除规则模板“${ruleSet.name}”吗？删除后不能从模板列表复用。`)
    if (!confirmed) return
    setDeletingRuleSetId(ruleSet.id)
    deleteRuleSetMutation.mutate(ruleSet.id, {
      onSuccess: () => {
        if (expandedRuleSetId === ruleSet.id) setExpandedRuleSetId(null)
        if (editingRuleSetId === ruleSet.id) cancelEditing()
      },
      onSettled: () => setDeletingRuleSetId(null),
    })
  }

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
          <>
            <div className="divide-y divide-neutral-200 md:hidden">
              {ruleSets.map((ruleSet) => {
                const isExpanded = expandedRuleSetId === ruleSet.id
                const isEditing = editingRuleSetId === ruleSet.id
                return (
                  <TemplateCard
                    key={ruleSet.id}
                    ruleSet={ruleSet}
                    isExpanded={isExpanded}
                    isEditing={isEditing}
                    draftName={draftName}
                    isSaving={updateRuleSetMutation.isPending && isEditing}
                    isDeleting={deletingRuleSetId === ruleSet.id}
                    renameError={
                      updateRuleSetMutation.isError && isEditing
                        ? updateRuleSetMutation.error.message
                        : null
                    }
                    onToggle={() => setExpandedRuleSetId(isExpanded ? null : ruleSet.id)}
                    onStartEditing={() => startEditing(ruleSet)}
                    onCancelEditing={cancelEditing}
                    onDraftNameChange={setDraftName}
                    onSubmitRename={submitRename}
                    onDelete={() => deleteRuleSet(ruleSet)}
                  />
                )
              })}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-sm">
              <thead className="bg-neutral-50">
                <tr>
                  <th className="w-12 px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-neutral-500">
                    明细
                  </th>
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
                  <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wider text-neutral-500">
                    操作
                  </th>
                </tr>
              </thead>
                <tbody className="divide-y divide-neutral-200">
                  {ruleSets.map((ruleSet) => {
                    const isExpanded = expandedRuleSetId === ruleSet.id
                    const isEditing = editingRuleSetId === ruleSet.id
                    return (
                      <TemplateRows
                        key={ruleSet.id}
                        ruleSet={ruleSet}
                        isExpanded={isExpanded}
                        isEditing={isEditing}
                        draftName={draftName}
                        isSaving={updateRuleSetMutation.isPending && isEditing}
                        isDeleting={deletingRuleSetId === ruleSet.id}
                        renameError={
                          updateRuleSetMutation.isError && isEditing
                            ? updateRuleSetMutation.error.message
                            : null
                        }
                        onToggle={() => setExpandedRuleSetId(isExpanded ? null : ruleSet.id)}
                        onStartEditing={() => startEditing(ruleSet)}
                        onCancelEditing={cancelEditing}
                        onDraftNameChange={setDraftName}
                        onSubmitRename={submitRename}
                        onDelete={() => deleteRuleSet(ruleSet)}
                      />
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-neutral-200 px-5 py-4">
              <p className="text-xs text-neutral-500">第 {page} 页，每页 {PAGE_SIZE} 条</p>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
                  disabled={offset === 0}
                >
                  上一页
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
                  disabled={ruleSets.length < PAGE_SIZE}
                >
                  下一页
                </Button>
              </div>
            </div>
          </>
        )}
      </section>

      {expandedRuleSet && (
        <section className="mt-5 hidden rounded-xl border border-neutral-200 bg-white shadow-sm md:block lg:hidden">
          <RuleDetails ruleSet={expandedRuleSet} />
        </section>
      )}
    </div>
  )
}
