import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import { AlertCircle, ArrowLeft, CheckCircle, Clock, Download } from 'lucide-react'
import { Button } from '@/shared/ui/Button'
import { useReportQuery, useExportReportMutation } from '@/features/reports/hooks'
import {
  filterFindings,
  groupFindingsByFragment,
  normalizeSeverity,
  type CategoryFilter,
  type SeverityFilter,
} from './reportFilters'
import {
  AnchorLink,
  DistributionPanel,
  FilterButton,
  FilterRow,
  ProblemSection,
  ScopePanel,
  SummaryPanel,
  buildFragmentSections,
  categoryFilters,
  severityFilters,
  useMediaQuery,
} from './ReportDetailSections'

export function ReportDetailPage() {
  const { reportId } = useParams<{ reportId: string }>()
  const [activeSeverity, setActiveSeverity] = useState<SeverityFilter>('all')
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>('all')
  const isDesktop = useMediaQuery('(min-width: 1024px)')

  const { data: report, isLoading } = useReportQuery(reportId || '')
  const exportReportMutation = useExportReportMutation()

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

  const handleExport = async () => {
    if (!reportId) return
    const exportData = await exportReportMutation.mutateAsync(reportId)
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
            <p className="mt-1 text-sm text-neutral-500">
              {report.document_filename || `历史文档 ${report.document_id}`}
            </p>
          </div>
        </div>
        <Button
          variant="secondary"
          onClick={() => void handleExport()}
          isLoading={exportReportMutation.isPending}
        >
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
              rulesetName={report.ruleset_name}
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
                  <ProblemSection key={section.id} section={section} isDesktop={isDesktop} />
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
