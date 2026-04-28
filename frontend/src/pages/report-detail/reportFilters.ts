import type { CheckFinding } from '@/entities/finding/model'

export type SeverityFilter = 'all' | 'major' | 'minor' | 'info'
export type CategoryFilter =
  | 'all'
  | 'font'
  | 'paragraph'
  | 'heading'
  | 'page'
  | 'header_footer'
  | 'caption'
  | 'reference'
  | 'structure'
  | 'toc'

export function filterFindings(
  findings: CheckFinding[],
  severity: SeverityFilter,
  category: CategoryFilter,
) {
  return findings.filter((finding) => {
    const matchSeverity = severity === 'all' || normalizeSeverity(finding.severity) === severity
    const matchCategory = category === 'all' || finding.category === category
    return matchSeverity && matchCategory
  })
}

export function categoryLabel(category: string | null | undefined) {
  return (
    {
      font: '字体',
      paragraph: '段落',
      heading: '标题',
      page: '页面',
      header_footer: '页眉页脚',
      caption: '图表题注',
      reference: '参考文献',
      structure: '结构',
      toc: '目录',
    }[category || ''] || '未分类'
  )
}

export function normalizeSeverity(severity: CheckFinding['severity']) {
  return severity === 'blocker' ? 'major' : severity
}

export interface FindingGroup {
  id: string
  title: string
  excerpt: string
  findings: CheckFinding[]
}

export function groupFindingsByFragment(findings: CheckFinding[]): FindingGroup[] {
  const groups = new Map<string, FindingGroup>()

  findings.forEach((finding) => {
    const key = locationLabel(finding)
    const existing = groups.get(key)
    if (existing) {
      existing.findings.push(finding)
      return
    }
    groups.set(key, {
      id: key,
      title: key,
      excerpt: finding.excerpt || '未提取到原文片段',
      findings: [finding],
    })
  })

  return Array.from(groups.values())
}

export function locationLabel(finding: CheckFinding) {
  if (finding.location.display_path) return finding.location.display_path
  if (finding.location.paragraph_number !== undefined && finding.location.paragraph_number !== null) {
    return `第 ${finding.location.paragraph_number} 段`
  }
  if (finding.location.paragraph_index !== undefined && finding.location.paragraph_index !== null) {
    return `第 ${finding.location.paragraph_index + 1} 段`
  }
  return finding.location.area || finding.location.section_path || '未定位'
}

export function findingFieldLabel(finding: CheckFinding) {
  const value = finding.context?.field_label
  return typeof value === 'string' && value ? value : finding.rule_id
}

export function formatFindingValue(values: Record<string, unknown>) {
  const entries = Object.entries(values)
  if (entries.length === 0) return '-'
  return entries.map(([key, value]) => `${key}: ${formatValue(value)}`).join('，')
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '未解析'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
