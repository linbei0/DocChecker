import type { CheckFinding } from '@/entities/finding/model'

export type SeverityFilter = 'all' | 'major' | 'minor' | 'info'
export type CategoryFilter = 'all' | 'font' | 'paragraph' | 'heading' | 'page'

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
