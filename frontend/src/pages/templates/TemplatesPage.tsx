import { useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import {
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Edit2,
  FileText,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  X,
} from 'lucide-react'
import {
  useDeleteRuleSetMutation,
  useRuleSetsQuery,
  useUpdateRuleSetMutation,
} from '@/features/rulesets/hooks'
import { type FormatRule, type RuleSet } from '@/entities/ruleset/model'
import { StatusBadge } from '@/shared/ui/StatusBadge'
import { Button } from '@/shared/ui/Button'
import { cn } from '@/shared/lib/utils'

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

type TemplateItemProps = {
  ruleSet: RuleSet
  isExpanded: boolean
  isEditing: boolean
  draftName: string
  isSaving: boolean
  isDeleting: boolean
  renameError: string | null
  onToggle: () => void
  onStartEditing: () => void
  onCancelEditing: () => void
  onDraftNameChange: (value: string) => void
  onSubmitRename: (event: FormEvent<HTMLFormElement>) => void
  onDelete: () => void
}

function TemplateCard({
  ruleSet,
  isExpanded,
  isEditing,
  draftName,
  isSaving,
  isDeleting,
  renameError,
  onToggle,
  onStartEditing,
  onCancelEditing,
  onDraftNameChange,
  onSubmitRename,
  onDelete,
}: TemplateItemProps) {
  return (
    <article className="px-5 py-4">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-50 text-primary-700">
          <FileText className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          {isEditing ? (
            <form className="space-y-2" onSubmit={onSubmitRename}>
              <input
                value={draftName}
                onChange={(event) => onDraftNameChange(event.target.value)}
                className="h-10 w-full rounded-lg border border-neutral-300 px-3 text-sm text-neutral-900 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                autoFocus
              />
              {renameError && <p className="text-xs text-danger-600">{renameError}</p>}
              <div className="flex flex-wrap gap-2">
                <Button size="sm" type="submit" isLoading={isSaving} disabled={!draftName.trim()}>
                  保存
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={onCancelEditing}>
                  取消
                </Button>
              </div>
            </form>
          ) : (
            <>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-medium text-neutral-950">{ruleSet.name}</h2>
                  <p className="mt-1 text-xs text-neutral-500">
                    {sourceText[ruleSet.source_type]} · {ruleSet.rules.length} 条规则
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onToggle}
                  className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-neutral-500 hover:bg-neutral-100 hover:text-primary-700"
                  aria-label={isExpanded ? '收起规则明细' : '查看规则明细'}
                  title={isExpanded ? '收起规则明细' : '查看规则明细'}
                >
                  {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </button>
              </div>
              <p className="mt-2 text-xs text-neutral-400">
                v{ruleSet.version} · {new Date(ruleSet.created_at).toLocaleString()}
              </p>
              <div className="mt-3 flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={onStartEditing}
                  className="text-sm text-primary-600 hover:underline"
                >
                  编辑名称
                </button>
                <button
                  type="button"
                  onClick={onDelete}
                  disabled={isDeleting}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-danger-50 hover:text-danger-600 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="删除规则模板"
                  title="删除规则模板"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </>
          )}
        </div>
      </div>
      {isExpanded && (
        <div className="mt-4 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
          <RuleDetails ruleSet={ruleSet} />
        </div>
      )}
    </article>
  )
}

function TemplateRows({
  ruleSet,
  isExpanded,
  isEditing,
  draftName,
  isSaving,
  isDeleting,
  renameError,
  onToggle,
  onStartEditing,
  onCancelEditing,
  onDraftNameChange,
  onSubmitRename,
  onDelete,
}: TemplateItemProps) {
  return (
    <>
      <tr className={cn('hover:bg-neutral-50', isExpanded && 'bg-primary-50/40')}>
        <td className="px-5 py-4 align-top">
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-neutral-500 hover:bg-white hover:text-primary-700"
            aria-label={isExpanded ? '收起规则明细' : '查看规则明细'}
            title={isExpanded ? '收起规则明细' : '查看规则明细'}
          >
            {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
        </td>
        <td className="min-w-[320px] px-5 py-4 align-top">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-50 text-primary-700">
              <FileText className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              {isEditing ? (
                <form className="space-y-2" onSubmit={onSubmitRename}>
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      value={draftName}
                      onChange={(event) => onDraftNameChange(event.target.value)}
                      className="h-9 min-w-0 flex-1 rounded-lg border border-neutral-300 px-3 text-sm text-neutral-900 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                      autoFocus
                    />
                    <Button size="sm" type="submit" isLoading={isSaving} disabled={!draftName.trim()}>
                      <Save className="mr-1.5 h-4 w-4" />
                      保存
                    </Button>
                    <Button type="button" variant="ghost" size="sm" onClick={onCancelEditing}>
                      <X className="mr-1.5 h-4 w-4" />
                      取消
                    </Button>
                  </div>
                  {renameError && <p className="text-xs text-danger-600">{renameError}</p>}
                </form>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <div>
                    <div className="font-medium text-neutral-900">{ruleSet.name}</div>
                    <div className="text-xs text-neutral-400">{ruleSet.id}</div>
                  </div>
                  <button
                    type="button"
                    onClick={onStartEditing}
                    className="inline-flex h-7 w-7 items-center justify-center rounded-md text-neutral-400 hover:bg-neutral-100 hover:text-primary-700"
                    aria-label="编辑模板名称"
                    title="编辑模板名称"
                  >
                    <Edit2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
            </div>
          </div>
        </td>
        <td className="px-5 py-4 align-top text-neutral-700">{sourceText[ruleSet.source_type]}</td>
        <td className="px-5 py-4 align-top text-neutral-700">{ruleSet.version}</td>
        <td className="px-5 py-4 align-top">
          <StatusBadge status="enabled" text={`${ruleSet.rules.length} 条`} />
        </td>
        <td className="px-5 py-4 align-top text-neutral-500">
          {new Date(ruleSet.created_at).toLocaleString()}
        </td>
        <td className="px-5 py-4 text-right align-top">
          <button
            type="button"
            onClick={onDelete}
            disabled={isDeleting}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-danger-50 hover:text-danger-600 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="删除规则模板"
            title="删除规则模板"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </td>
      </tr>
      {isExpanded && (
        <tr className="hidden bg-white lg:table-row">
          <td colSpan={7} className="border-t border-primary-100 px-5 py-5">
            <RuleDetails ruleSet={ruleSet} />
          </td>
        </tr>
      )}
    </>
  )
}

function RuleDetails({ ruleSet }: { ruleSet: RuleSet }) {
  return (
    <div>
      <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">规则明细</h3>
          <p className="mt-1 text-xs text-neutral-500">
            展示每条模板规则的检查对象、期望值和来源依据。
          </p>
        </div>
        <p className="text-xs text-neutral-500">模板 ID：{ruleSet.id}</p>
      </div>

      {ruleSet.rules.length === 0 ? (
        <div className="rounded-lg border border-dashed border-neutral-300 px-4 py-8 text-center text-sm text-neutral-500">
          这个模板还没有规则。
        </div>
      ) : (
        <div className="grid gap-3">
          {ruleSet.rules.map((rule, index) => (
            <RuleCard key={rule.id} rule={rule} index={index} />
          ))}
        </div>
      )}
    </div>
  )
}

function RuleCard({ rule, index }: { rule: FormatRule; index: number }) {
  const capabilityStatus = rule.capability_status || 'auto_checkable'

  return (
    <article className="rounded-lg border border-neutral-200 bg-neutral-50 px-4 py-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-white px-2 py-1 text-xs font-medium text-neutral-500">
              #{index + 1}
            </span>
            <span className="font-medium text-neutral-950">{categoryText[rule.category] || rule.category}</span>
            <span className="rounded-full bg-white px-2.5 py-1 text-xs text-neutral-600">
              {severityText[rule.severity] || rule.severity}
            </span>
            <span className="rounded-full bg-primary-50 px-2.5 py-1 text-xs text-primary-700">
              {capabilityText[capabilityStatus] || capabilityStatus}
            </span>
          </div>
          <p className="mt-2 break-all text-xs text-neutral-400">{rule.id}</p>
        </div>
      </div>

      <dl className="mt-4 grid gap-3 text-sm lg:grid-cols-[1fr_1.4fr_1.4fr]">
        <InfoBlock label="检查对象" value={formatTarget(rule)} />
        <InfoBlock label="期望规则" value={formatRecord(rule.expectation)} />
        <InfoBlock label="容差" value={formatRecord(rule.tolerance)} mutedWhenEmpty />
      </dl>

      <div className="mt-4 rounded-lg bg-white px-3 py-3 text-sm">
        <div className="mb-1 text-xs font-medium text-neutral-500">来源依据</div>
        <p className="whitespace-pre-wrap break-words text-neutral-800">{rule.source.excerpt || '未记录来源文本'}</p>
        {rule.source.location && (
          <p className="mt-2 text-xs text-neutral-500">位置：{rule.source.location}</p>
        )}
      </div>
    </article>
  )
}

function InfoBlock({
  label,
  value,
  mutedWhenEmpty,
}: {
  label: string
  value: string
  mutedWhenEmpty?: boolean
}) {
  const isEmpty = value === '-'
  return (
    <div className="rounded-lg bg-white px-3 py-3">
      <dt className="mb-1 text-xs font-medium text-neutral-500">{label}</dt>
      <dd className={cn('whitespace-pre-wrap break-words text-neutral-900', isEmpty && mutedWhenEmpty && 'text-neutral-400')}>
        {value}
      </dd>
    </div>
  )
}

function formatTarget(rule: FormatRule) {
  return [targetScopeText[rule.target.scope] || rule.target.scope, rule.target.selector]
    .filter(Boolean)
    .join(' / ')
}

function formatRecord(record: Record<string, unknown> | undefined) {
  if (!record || Object.keys(record).length === 0) return '-'
  return Object.entries(record)
    .map(([key, value]) => `${fieldText[key] || key}：${formatValue(key, value)}`)
    .join('\n')
}

function formatValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (Array.isArray(value)) return value.map((item) => formatValue(key, item)).join('、')
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  if (typeof value === 'boolean') return value ? '是' : '否'
  const unit = fieldUnitText[key]
  return unit ? `${String(value)} ${unit}` : String(value)
}

const sourceText = {
  manual: '手动输入',
  requirement_doc: '格式规范文档',
  template: '模板复制',
}

const categoryText: Record<string, string> = {
  font: '字体',
  paragraph: '段落',
  heading: '标题',
  page: '页面',
  header_footer: '页眉页脚',
  caption: '图表题注',
  reference: '参考文献',
  structure: '结构',
  toc: '目录',
  abstract: '摘要',
}

const severityText: Record<string, string> = {
  blocker: '阻断',
  major: '严重',
  minor: '一般',
  info: '提示',
}

const capabilityText: Record<string, string> = {
  auto_checkable: '可自动检查',
  needs_confirmation: '需确认',
  unsupported: '暂不支持',
  conflict: '规则冲突',
  parse_error: '解析异常',
}

const targetScopeText: Record<string, string> = {
  document: '全文',
  section: '章节',
  paragraph: '段落',
  heading: '标题',
  table: '表格',
  header_footer: '页眉页脚',
  caption: '图表题注',
  reference: '参考文献',
  toc: '目录',
  abstract: '摘要',
  page: '页面',
}

const fieldText: Record<string, string> = {
  fontFamilyEastAsia: '中文字体',
  fontFamilyAscii: '英文字体',
  fontSizePt: '字号',
  firstLineIndentCm: '首行缩进',
  lineSpacing: '行距',
  spaceBeforePt: '段前',
  spaceAfterPt: '段后',
  textContains: '必须包含文本',
  requiresPageNumber: '必须包含页码',
  captionPattern: '题注编号格式',
  requiresTableCaption: '表格题注',
  requiresFigureCaption: '图片题注',
  tableCaptionPosition: '表题位置',
  figureCaptionPosition: '图题位置',
  font_family: '字体',
  font_family_east_asia: '中文字体',
  font_family_ascii: '西文字体',
  font_size_pt: '字号',
  bold: '加粗',
  alignment: '对齐',
  first_line_indent_cm: '首行缩进',
  line_spacing: '行距',
  space_before_pt: '段前',
  space_after_pt: '段后',
  margin_top_cm: '上边距',
  margin_bottom_cm: '下边距',
  margin_left_cm: '左边距',
  margin_right_cm: '右边距',
  page_width_cm: '页面宽度',
  page_height_cm: '页面高度',
  header_distance_cm: '页眉距边界',
  footer_distance_cm: '页脚距边界',
}

const fieldUnitText: Record<string, string> = {
  fontSizePt: 'pt',
  firstLineIndentCm: 'cm',
  spaceBeforePt: 'pt',
  spaceAfterPt: 'pt',
  font_size_pt: 'pt',
  first_line_indent_cm: 'cm',
  space_before_pt: 'pt',
  space_after_pt: 'pt',
  margin_top_cm: 'cm',
  margin_bottom_cm: 'cm',
  margin_left_cm: 'cm',
  margin_right_cm: 'cm',
  page_width_cm: 'cm',
  page_height_cm: 'cm',
  header_distance_cm: 'cm',
  footer_distance_cm: 'cm',
}
