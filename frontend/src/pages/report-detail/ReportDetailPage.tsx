import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Link, useParams } from 'react-router'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle,
  Clock,
  Download,
  FileText,
  Layers,
  ListChecks,
} from 'lucide-react'
import { Button } from '@/shared/ui/Button'
import { useReportQuery, useExportReportQuery } from '@/features/reports/hooks'
import { cn } from '@/shared/lib/utils'
import {
  categoryLabel,
  filterFindings,
  findingFieldLabel,
  formatFindingValue,
  groupFindingsByFragment,
  normalizeSeverity,
  type CategoryFilter,
  type SeverityFilter,
} from './reportFilters'

const severityFilters: Array<{ key: SeverityFilter; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'major', label: '严重' },
  { key: 'minor', label: '一般' },
  { key: 'info', label: '提示' },
]

const categoryFilters: Array<{ key: CategoryFilter; label: string }> = [
  { key: 'all', label: '全部类别' },
  { key: 'font', label: '字体' },
  { key: 'paragraph', label: '段落' },
  { key: 'heading', label: '标题' },
  { key: 'page', label: '页面' },
  { key: 'reference', label: '参考文献' },
  { key: 'structure', label: '结构' },
  { key: 'toc', label: '目录' },
  { key: 'abstract', label: '摘要' },
]

export function ReportDetailPage() {
  const { reportId } = useParams<{ reportId: string }>()
  const [activeSeverity, setActiveSeverity] = useState<SeverityFilter>('all')
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>('all')

  const { data: report, isLoading } = useReportQuery(reportId || '')
  const { data: exportData } = useExportReportQuery(reportId || '')

  const summary = useMemo(() => {
    if (!report) return { total: 0, major: 0, minor: 0, info: 0 }
    const findings = report.findings
    return {
      total: findings.length,
      major: findings.filter((f) => normalizeSeverity(f.severity) === 'major').length,
      minor: findings.filter((f) => normalizeSeverity(f.severity) === 'minor').length,
      info: findings.filter((f) => normalizeSeverity(f.severity) === 'info').length,
    }
  }, [report])

  const score = useMemo(() => {
    return Math.max(0, 100 - summary.major * 8 - summary.minor * 3 - summary.info)
  }, [summary])

  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>()
    report?.findings.forEach((finding) => {
      const category = finding.category || 'uncategorized'
      counts.set(category, (counts.get(category) || 0) + 1)
    })
    return counts
  }, [report])

  const filteredFindings = useMemo(() => {
    if (!report) return []
    return filterFindings(report.findings, activeSeverity, activeCategory)
  }, [report, activeSeverity, activeCategory])

  const findingGroups = useMemo(() => groupFindingsByFragment(filteredFindings), [filteredFindings])
  const fragmentSections = useMemo(() => buildFragmentSections(findingGroups), [findingGroups])

  const handleExport = () => {
    if (!exportData?.content) return
    const blob = new Blob([exportData.content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `report-${reportId}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 text-center">
        <div className="inline-flex items-center gap-2 text-neutral-500">
          <Clock className="h-5 w-5 animate-spin" />
          <span>加载报告中...</span>
        </div>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 text-center">
        <AlertCircle className="mx-auto h-10 w-10 text-neutral-400" />
        <p className="mt-4 text-neutral-600">报告不存在或已过期</p>
        <Link to="/checks/new" className="mt-4 inline-block text-primary-600 hover:underline">
          返回新建检查
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link to="/checks/new" className="rounded-lg p-2 text-neutral-500 hover:bg-neutral-100">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-semibold text-neutral-950">检查报告</h1>
            <p className="mt-1 text-sm text-neutral-500">{report.document_id}</p>
          </div>
        </div>
        <Button variant="secondary" onClick={handleExport}>
          <Download className="mr-1 h-4 w-4" />
          导出 Markdown
        </Button>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_260px]">
        <main className="space-y-6">
          <section id="document-info" className="grid gap-4 lg:grid-cols-3">
            <SummaryPanel score={score} summary={summary} />
            <DistributionPanel summary={summary} />
            <ScopePanel
              checkerVersion={report.checker_version}
              generatedAt={report.generated_at}
              rulesetId={report.ruleset_id}
            />
          </section>

          <section id="check-result" className="rounded-lg border border-neutral-200 bg-white shadow-sm">
            <div className="border-b border-neutral-200 px-5 py-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-primary-700">检测结果</p>
                  <h2 className="mt-1 text-lg font-semibold text-neutral-950">问题分类</h2>
                </div>
                <p className="text-sm text-neutral-500">
                  当前显示 {filteredFindings.length} / {report.findings.length} 个问题
                </p>
              </div>
            </div>

            <div className="space-y-5 px-5 py-5">
              <FilterRow label="严重程度">
                {severityFilters.map((filter) => (
                  <FilterButton
                    key={filter.key}
                    active={activeSeverity === filter.key}
                    label={filter.label}
                    count={filter.key === 'all' ? summary.total : summary[filter.key]}
                    onClick={() => setActiveSeverity(filter.key)}
                  />
                ))}
              </FilterRow>
              <FilterRow label="规则类别">
                {categoryFilters.map((filter) => (
                  <FilterButton
                    key={filter.key}
                    active={activeCategory === filter.key}
                    label={filter.label}
                    count={
                      filter.key === 'all'
                        ? summary.total
                        : categoryCounts.get(filter.key) || 0
                    }
                    onClick={() => setActiveCategory(filter.key)}
                  />
                ))}
              </FilterRow>
            </div>
          </section>

          <section id="fragments" className="overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm">
            <div className="relative border-b border-neutral-100 px-6 pb-5 pt-6">
              <div className="absolute left-0 top-0 rounded-br-[36px] bg-primary-50 px-7 py-3">
                <h2 className="text-2xl font-semibold text-primary-700">问题片段</h2>
              </div>
              <p className="pt-14 text-sm text-neutral-500">
                按论文部分和段落聚合，同一段的多个问题合并展示
              </p>
            </div>

            {findingGroups.length === 0 ? (
              <div className="px-6 py-12 text-center text-neutral-400">
                <CheckCircle className="mx-auto mb-2 h-8 w-8" />
                <p>没有符合条件的问题</p>
              </div>
            ) : (
              <div className="space-y-11 px-6 py-8">
                {fragmentSections.map((section) => (
                  <ProblemSection key={section.id} section={section} />
                ))}
              </div>
            )}
          </section>
        </main>

        <aside className="xl:sticky xl:top-6 xl:self-start">
          <nav className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
            <p className="mb-3 text-sm font-semibold text-neutral-950">报告目录</p>
            <div className="space-y-2 text-sm">
              <AnchorLink href="#document-info" label="文档信息" />
              <AnchorLink href="#check-result" label="检测结果" />
              <AnchorLink href="#fragments" label="问题片段" count={filteredFindings.length} />
            </div>
            <div className="mt-4 border-t border-neutral-200 pt-4">
              <p className="mb-2 text-xs font-medium text-neutral-500">问题分组</p>
              <div className="max-h-[52vh] space-y-2 overflow-y-auto pr-1">
                {fragmentSections.slice(0, 30).map((section, index) => (
                  <a
                    key={section.id}
                    href={`#fragment-section-${index}`}
                    className="block rounded-md px-2 py-1.5 text-xs text-neutral-600 hover:bg-neutral-100 hover:text-neutral-950"
                  >
                    <span className="line-clamp-2">{section.title}</span>
                    <span className="text-danger-600">{section.total} 个问题</span>
                  </a>
                ))}
              </div>
            </div>
          </nav>
        </aside>
      </div>
    </div>
  )
}

function SummaryPanel({
  score,
  summary,
}: {
  score: number
  summary: { total: number; major: number; minor: number; info: number }
}) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-4">
        <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-primary-50">
          <span className="text-3xl font-bold text-primary-700">{Math.round(score)}</span>
        </div>
        <div>
          <p className="text-sm text-neutral-500">总体评分</p>
          <p className="mt-1 text-2xl font-semibold text-neutral-950">
            {score >= 80 ? '良好' : score >= 60 ? '一般' : '需改进'}
          </p>
          <p className="mt-2 text-sm text-neutral-500">共发现 {summary.total} 个格式问题</p>
        </div>
      </div>
    </div>
  )
}

function DistributionPanel({
  summary,
}: {
  summary: { total: number; major: number; minor: number; info: number }
}) {
  const items = [
    { label: '严重', count: summary.major, className: 'bg-warning-50 text-warning-700' },
    { label: '一般', count: summary.minor, className: 'bg-primary-50 text-primary-700' },
    { label: '提示', count: summary.info, className: 'bg-neutral-100 text-neutral-600' },
    { label: '总计', count: summary.total, className: 'bg-success-50 text-success-700' },
  ]

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <ListChecks className="h-4 w-4 text-primary-600" />
        <p className="text-sm font-medium text-neutral-950">问题分布</p>
      </div>
      <div className="grid grid-cols-4 gap-2 text-center">
        {items.map((item) => (
          <div key={item.label} className={cn('rounded-lg px-2 py-3', item.className)}>
            <div className="text-2xl font-bold">{item.count}</div>
            <div className="text-xs">{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ScopePanel({
  rulesetId,
  checkerVersion,
  generatedAt,
}: {
  rulesetId: string
  checkerVersion?: string
  generatedAt?: string
}) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <FileText className="h-4 w-4 text-primary-600" />
        <p className="text-sm font-medium text-neutral-950">检查范围</p>
      </div>
      <dl className="space-y-3 text-sm">
        <InfoLine label="规则集" value={rulesetId} />
        <InfoLine label="检查器版本" value={checkerVersion || '-'} />
        <InfoLine
          label="检查时间"
          value={generatedAt ? new Date(generatedAt).toLocaleString() : '-'}
        />
      </dl>
    </div>
  )
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-neutral-500">{label}</dt>
      <dd className="break-all text-right font-medium text-neutral-900">{value}</dd>
    </div>
  )
}

function FilterRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
      <span className="w-20 shrink-0 text-sm text-neutral-500">{label}：</span>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  )
}

function FilterButton({
  active,
  label,
  count,
  onClick,
}: {
  active: boolean
  label: string
  count: number
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
        active ? 'bg-primary-50 text-primary-700' : 'text-neutral-600 hover:bg-neutral-100',
      )}
    >
      <span>{label}</span>
      <span className="text-xs opacity-75">{count}</span>
    </button>
  )
}

type FindingGroup = ReturnType<typeof groupFindingsByFragment>[number]
type DisplayFindingGroup = FindingGroup & { displayIndex: number; anchorIndex: number }

interface FragmentSection {
  id: string
  title: string
  groups: DisplayFindingGroup[]
  major: number
  minor: number
  info: number
  total: number
}

function buildFragmentSections(groups: FindingGroup[]): FragmentSection[] {
  const sections = new Map<string, FragmentSection>()
  let displayIndex = 1

  groups.forEach((group, anchorIndex) => {
    const title = fragmentSectionTitle(group)
    const section = sections.get(title) || {
      id: title,
      title,
      groups: [],
      major: 0,
      minor: 0,
      info: 0,
      total: 0,
    }

    group.findings.forEach((finding) => {
      const severity = normalizeSeverity(finding.severity)
      section[severity] += 1
      section.total += 1
    })
    section.groups.push({ ...group, displayIndex, anchorIndex })
    sections.set(title, section)
    displayIndex += 1
  })

  return Array.from(sections.values())
}

function fragmentSectionTitle(group: FindingGroup) {
  const first = group.findings[0]
  return first.location.section_name || first.location.section_path || categoryLabel(first.category)
}

function ProblemSection({ section }: { section: FragmentSection }) {
  return (
    <article id={`fragment-section-${section.groups[0]?.anchorIndex ?? 0}`}>
      <div className="mb-5 flex items-center justify-between gap-4">
        <h3 className="flex items-center gap-3 text-xl font-semibold text-neutral-950">
          <span className="h-5 w-1 rounded-full bg-primary-600" />
          {section.title}
        </h3>
        <div className="flex flex-wrap items-center justify-end gap-4 text-sm">
          {section.major > 0 && <SeverityCount tone="danger" label="严重错误" count={section.major} />}
          {section.minor > 0 && <SeverityCount tone="danger" label="一般错误" count={section.minor} />}
          {section.info > 0 && <SeverityCount tone="info" label="提醒" count={section.info} />}
        </div>
      </div>

      <div className="overflow-hidden border border-neutral-200">
        <table className="hidden w-full table-fixed border-collapse text-sm lg:table">
          <colgroup>
            <col className="w-20" />
            <col className="w-[22%]" />
            <col className="w-[20%]" />
            <col className="w-[25%]" />
            <col />
          </colgroup>
          <thead className="bg-[#dfe8f1] text-left text-neutral-950">
            <tr>
              <th className="px-5 py-3 font-semibold">序号</th>
              <th className="border-l border-[#d2dde8] px-5 py-3 font-semibold">原文片段</th>
              <th className="border-l border-[#d2dde8] px-5 py-3 font-semibold">问题详情</th>
              <th className="border-l border-[#d2dde8] px-5 py-3 font-semibold">原文问题描述</th>
              <th className="border-l border-[#d2dde8] px-5 py-3 font-semibold">规范</th>
            </tr>
          </thead>
          <tbody>
            {section.groups.map((group) =>
              group.findings.map((finding, issueIndex) => (
                <tr
                  key={finding.id}
                  className={cn(
                    'border-t border-neutral-200',
                    group.displayIndex % 2 === 0 && 'bg-neutral-50',
                  )}
                >
                  {issueIndex === 0 && (
                    <>
                      <td rowSpan={group.findings.length} className="px-5 py-4 text-center align-middle">
                        {group.displayIndex}
                      </td>
                      <td
                        rowSpan={group.findings.length}
                        className="border-l border-neutral-200 px-5 py-4 align-middle text-neutral-900"
                      >
                        <Tooltip content={group.excerpt}>
                          <span className="line-clamp-4">{group.excerpt}</span>
                        </Tooltip>
                      </td>
                    </>
                  )}
                  <td className="border-l border-neutral-200 px-5 py-3 align-top">
                    <IssueDetail finding={finding} />
                  </td>
                  <td className="border-l border-neutral-200 px-5 py-3 align-top text-neutral-800">
                    <span className="line-clamp-2">{formatFindingValue(finding.actual)}</span>
                  </td>
                  <td className="border-l border-neutral-200 px-5 py-3 align-top text-primary-700">
                    <span className="line-clamp-2">{formatFindingValue(finding.expected)}</span>
                  </td>
                </tr>
              )),
            )}
          </tbody>
        </table>

        <div className="divide-y divide-neutral-200 lg:hidden">
          {section.groups.map((group) => (
            <MobileFragmentCard key={group.id} group={group} />
          ))}
        </div>
      </div>
    </article>
  )
}

function SeverityCount({
  tone,
  label,
  count,
}: {
  tone: 'danger' | 'info'
  label: string
  count: number
}) {
  return (
    <span className={tone === 'danger' ? 'text-danger-600' : 'text-primary-600'}>
      <span className="mr-1 inline-flex h-4 w-4 items-center justify-center rounded-full border text-[10px] leading-none">
        ×
      </span>
      {label}： {count}种
    </span>
  )
}

function IssueDetail({
  finding,
}: {
  finding: FindingGroup['findings'][number]
}) {
  return (
    <div className="flex items-center gap-2 text-neutral-900">
      <span
        className={cn(
          'h-2 w-2 shrink-0',
          normalizeSeverity(finding.severity) === 'info' ? 'bg-primary-600' : 'bg-danger-500',
        )}
      />
      <span className="line-clamp-2">{findingFieldLabel(finding)}</span>
      {finding.status && finding.status !== 'mismatch' && (
        <span className="shrink-0 rounded border border-neutral-300 px-1.5 py-0.5 text-xs text-neutral-600">
          {findingStatusLabel(finding.status)}
        </span>
      )}
    </div>
  )
}

function Tooltip({ content, children }: { content: string; children: React.ReactNode }) {
  const [visible, setVisible] = useState(false)
  const triggerRef = useRef<HTMLSpanElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })

  const updatePosition = () => {
    if (!triggerRef.current || !tooltipRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const tooltipRect = tooltipRef.current.getBoundingClientRect()
    let top = rect.bottom + 8
    let left = rect.left

    if (left + tooltipRect.width > window.innerWidth - 16) {
      left = window.innerWidth - tooltipRect.width - 16
    }
    if (left < 16) left = 16
    if (top + tooltipRect.height > window.innerHeight - 16) {
      top = rect.top - tooltipRect.height - 8
    }

    setPos({ top, left })
  }

  useEffect(() => {
    if (visible) {
      const raf = requestAnimationFrame(updatePosition)
      return () => cancelAnimationFrame(raf)
    }
  }, [visible])

  const handleEnter = () => {
    setVisible(true)
  }

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={handleEnter}
        onMouseLeave={() => setVisible(false)}
        onFocus={handleEnter}
        onBlur={() => setVisible(false)}
        className="cursor-help"
      >
        {children}
      </span>
      {visible &&
        createPortal(
          <div
            ref={tooltipRef}
            className="fixed z-[9999] max-w-md rounded-xl border border-neutral-700 bg-neutral-800 px-4 py-3 text-sm leading-relaxed text-white shadow-2xl"
            style={{ top: pos.top, left: pos.left }}
          >
            {content}
          </div>,
          document.body,
        )}
    </>
  )
}

function findingStatusLabel(status: FindingGroup['findings'][number]['status']) {
  if (!status) return '不一致'
  return (
    {
      missing_actual: '未解析',
      mixed_value: '混合值',
      unsupported_field: '暂不支持',
      mismatch: '不一致',
      mixed_script_ok: '混排正常',
      needs_confirmation: '需确认',
    }[status] || '不一致'
  )
}

function MobileFragmentCard({ group }: { group: DisplayFindingGroup }) {
  return (
    <div className="space-y-4 px-4 py-5 text-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-neutral-100 font-semibold">
          {group.displayIndex}
        </span>
        <p className="text-neutral-900">{group.excerpt}</p>
      </div>
      <div className="space-y-3 pl-10">
        {group.findings.map((finding) => (
          <div key={finding.id} className="space-y-1">
            <IssueDetail finding={finding} />
            <p className="text-neutral-700">原文：{formatFindingValue(finding.actual)}</p>
            <p className="text-primary-700">规范：{formatFindingValue(finding.expected)}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function AnchorLink({ href, label, count }: { href: string; label: string; count?: number }) {
  return (
    <a
      href={href}
      className="flex items-center justify-between rounded-md px-2 py-1.5 text-neutral-700 hover:bg-neutral-100 hover:text-neutral-950"
    >
      <span className="inline-flex items-center gap-2">
        <Layers className="h-3.5 w-3.5 text-primary-600" />
        {label}
      </span>
      {count !== undefined && <span className="text-danger-600">{count}</span>}
    </a>
  )
}
