import { useParams } from 'react-router'
import { Download, AlertCircle, CheckCircle, Clock, ArrowLeft } from 'lucide-react'
import { Button } from '@/shared/ui/Button'
import { SeverityBadge } from '@/shared/ui/SeverityBadge'
import { useReportQuery, useExportReportQuery } from '@/features/reports/hooks'
import { cn } from '@/shared/lib/utils'
import { useState, useMemo } from 'react'
import { Link } from 'react-router'
import {
  categoryLabel,
  filterFindings,
  normalizeSeverity,
  type CategoryFilter,
  type SeverityFilter,
} from './reportFilters'

const severityFilters = [
  { key: 'all', label: '全部' },
  { key: 'major', label: '严重' },
  { key: 'minor', label: '一般' },
  { key: 'info', label: '提示' },
]

const categoryFilters = [
  { key: 'all', label: '全部类别' },
  { key: 'font', label: '字体' },
  { key: 'paragraph', label: '段落' },
  { key: 'heading', label: '标题' },
  { key: 'page', label: '页面' },
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
    return Math.max(0, 100 - summary.major * 8 - summary.minor * 3 - summary.info * 1)
  }, [summary])

  const filteredFindings = useMemo(() => {
    if (!report) return []
    return filterFindings(report.findings, activeSeverity, activeCategory)
  }, [report, activeSeverity, activeCategory])

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
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/checks/new" className="p-2 rounded-lg hover:bg-neutral-200 text-neutral-500">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-lg font-semibold text-neutral-900">检查报告</h1>
            <p className="text-sm text-neutral-500">{report.document_id}</p>
          </div>
        </div>
        <Button variant="secondary" onClick={handleExport}>
          <Download className="h-4 w-4 mr-1" />
          导出 Markdown
        </Button>
      </div>

      {/* Score & Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="bg-white rounded-xl border border-neutral-200 p-6 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-50">
              <span className="text-2xl font-bold text-primary-700">{Math.round(score)}</span>
            </div>
            <div>
              <p className="text-sm text-neutral-500">总体评分</p>
              <p className="text-lg font-semibold text-neutral-900">{score >= 80 ? '良好' : score >= 60 ? '一般' : '需改进'}</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-neutral-200 p-6 shadow-sm">
          <p className="text-sm font-medium text-neutral-900 mb-3">问题分布</p>
          <div className="grid grid-cols-4 gap-2 text-center">
            {[
              { label: '严重', count: summary.major, color: 'text-warning-600 bg-warning-50' },
              { label: '一般', count: summary.minor, color: 'text-primary-600 bg-primary-50' },
              { label: '提示', count: summary.info, color: 'text-neutral-600 bg-neutral-100' },
              { label: '总计', count: summary.total, color: 'text-success-600 bg-success-50' },
            ].map((item) => (
              <div key={item.label} className={cn('rounded-lg py-2', item.color)}>
                <div className="text-lg font-bold">{item.count}</div>
                <div className="text-xs">{item.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-neutral-200 p-6 shadow-sm">
          <p className="text-sm font-medium text-neutral-900 mb-3">检查范围</p>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-neutral-500">规则集</span>
              <span className="font-medium">{report.ruleset_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-500">检查器版本</span>
              <span className="font-medium">{report.checker_version || '-'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-500">检查时间</span>
              <span className="font-medium">{report.generated_at ? new Date(report.generated_at).toLocaleString() : '-'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-neutral-200 shadow-sm mb-6">
        <div className="p-4 border-b border-neutral-200 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-neutral-500">严重程度：</span>
            <div className="flex gap-1">
              {severityFilters.map((f) => (
                <button
                  key={f.key}
                  onClick={() => setActiveSeverity(f.key as SeverityFilter)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                    activeSeverity === f.key
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-neutral-600 hover:bg-neutral-100',
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-neutral-500">规则类别：</span>
            <div className="flex gap-1">
              {categoryFilters.map((f) => (
                <button
                  key={f.key}
                  onClick={() => setActiveCategory(f.key as CategoryFilter)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                    activeCategory === f.key
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-neutral-600 hover:bg-neutral-100',
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <div className="ml-auto text-sm text-neutral-500">
            当前显示 {filteredFindings.length} / {report.findings.length} 个问题
          </div>
        </div>

        {/* Findings Table */}
        {filteredFindings.length === 0 ? (
          <div className="px-6 py-12 text-center text-neutral-400">
            <CheckCircle className="mx-auto mb-2 h-8 w-8" />
            <p>没有符合条件的问题</p>
          </div>
        ) : (
        <div key={`${activeSeverity}-${activeCategory}`} className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">严重程度</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">类别</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">规则</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">位置</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">期望值</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">实际值</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">证据</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">建议</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200">
              {filteredFindings.map((finding) => (
                  <tr key={finding.id} className="hover:bg-neutral-50 transition-colors">
                    <td className="px-6 py-4">
                      <SeverityBadge severity={normalizeSeverity(finding.severity)} />
                    </td>
                    <td className="px-6 py-4 text-neutral-700">{categoryLabel(finding.category)}</td>
                    <td className="px-6 py-4 text-neutral-900 font-medium">{finding.rule_id}</td>
                    <td className="px-6 py-4 text-neutral-700">
                      {finding.location.section_path || '-'}
                      {finding.location.paragraph_index !== undefined && finding.location.paragraph_index !== null && (
                        <span className="text-neutral-400 ml-1">第{finding.location.paragraph_index}段</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-success-600 text-xs">
                      {JSON.stringify(finding.expected)}
                    </td>
                    <td className="px-6 py-4 text-danger-600 text-xs">
                      {JSON.stringify(finding.actual)}
                    </td>
                    <td className="px-6 py-4 text-neutral-600 text-xs max-w-xs">{finding.evidence}</td>
                    <td className="px-6 py-4 text-neutral-600 text-xs max-w-xs">{finding.suggestion}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        )}
      </div>
    </div>
  )
}
