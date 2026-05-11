import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { FileText, Layers, ListChecks } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import {
  categoryLabel,
  findingFieldLabel,
  formatFindingValue,
  groupFindingsByFragment,
  normalizeSeverity,
  type CategoryFilter,
  type SeverityFilter,
} from './reportFilters'

export const severityFilters: Array<{ key: SeverityFilter; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'major', label: '严重' },
  { key: 'minor', label: '一般' },
  { key: 'info', label: '提示' },
]

export const categoryFilters: Array<{ key: CategoryFilter; label: string }> = [
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

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  )

  useEffect(() => {
    const mediaQuery = window.matchMedia(query)
    setMatches(mediaQuery.matches)
    const handleChange = (event: MediaQueryListEvent) => setMatches(event.matches)
    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [query])

  return matches
}

export function SummaryPanel({
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

export function DistributionPanel({
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

export function ScopePanel({
  rulesetId,
  rulesetName,
  checkerVersion,
  generatedAt,
}: {
  rulesetId: string
  rulesetName?: string | null
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
        <InfoLine label="规则集" value={rulesetName || `历史规则集 ${rulesetId}`} />
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

export function FilterRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
      <span className="w-20 shrink-0 text-sm text-neutral-500">{label}：</span>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  )
}

export function FilterButton({
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

export function buildFragmentSections(groups: FindingGroup[]): FragmentSection[] {
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

export function ProblemSection({
  section,
  isDesktop,
}: {
  section: FragmentSection
  isDesktop: boolean
}) {
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
        {isDesktop ? (
          <table className="w-full table-fixed border-collapse text-sm">
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
        ) : (
          <div className="divide-y divide-neutral-200">
            {section.groups.map((group) => (
              <MobileFragmentCard key={group.id} group={group} />
            ))}
          </div>
        )}
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

function Tooltip({ content, children }: { content: string; children: ReactNode }) {
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

export function AnchorLink({ href, label, count }: { href: string; label: string; count?: number }) {
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
