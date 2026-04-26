import { useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { ArrowLeft, ArrowRight, CheckCircle, XCircle, Edit2 } from 'lucide-react'
import { Button } from '@/shared/ui/Button'
import { SeverityBadge } from '@/shared/ui/SeverityBadge'
import { cn } from '@/shared/lib/utils'
import type { FormatRule } from '@/entities/ruleset/model'

const mockRules: FormatRule[] = [
  {
    id: 'body_font',
    category: 'font',
    target: { scope: 'body.paragraph', selector: '正文' },
    expectation: { fontFamilyEastAsia: '宋体', fontSizePt: 12, bold: false },
    severity: 'major',
    source: { type: 'requirement_doc', excerpt: '正文采用宋体小四号字', location: '第 2 节第 3 段' },
    enabled: true,
  },
  {
    id: 'line_spacing',
    category: 'paragraph',
    target: { scope: 'body.paragraph', selector: '正文' },
    expectation: { lineSpacing: 1.5 },
    severity: 'major',
    source: { type: 'requirement_doc', excerpt: '行距 1.5 倍行距', location: '第 2 节第 4 段' },
    enabled: true,
  },
  {
    id: 'heading1',
    category: 'heading',
    target: { scope: 'heading.1', selector: '一级标题' },
    expectation: { fontFamilyEastAsia: '黑体', fontSizePt: 16, bold: true },
    severity: 'major',
    source: { type: 'requirement_doc', excerpt: '一级标题黑体三号居中', location: '第 3 节第 1 段' },
    enabled: true,
  },
  {
    id: 'heading2_conflict',
    category: 'heading',
    target: { scope: 'heading.2', selector: '二级标题' },
    expectation: { fontFamilyEastAsia: '黑体', fontSizePt: 14 },
    severity: 'major',
    source: { type: 'requirement_doc', excerpt: '二级标题黑体小三', location: '第 3 节第 2 段' },
    enabled: false,
  },
]

export function RuleConfirmPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [rules, setRules] = useState<FormatRule[]>(mockRules)
  const [expandedRule, setExpandedRule] = useState<string | null>(null)

  const toggleRule = (id: string) => {
    setRules((prev) =>
      prev.map((r) => (r.id === id ? { ...r, enabled: !r.enabled } : r)),
    )
  }

  const enabledCount = rules.filter((r) => r.enabled).length

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-neutral-900">确认规则</h1>
          <p className="text-sm text-neutral-500 mt-1">系统已从所选来源中提取出以下规则，请确认或调整</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            返回上一步
          </Button>
          <Button onClick={() => navigate(`/checks/${taskId}/progress`)}>
            确认并检查
            <ArrowRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-neutral-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-neutral-900">规则列表</span>
            <span className="text-xs text-neutral-500">({enabledCount}/{rules.length} 条已启用)</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm">
              <CheckCircle className="h-4 w-4 mr-1" />
              全部启用
            </Button>
            <Button variant="ghost" size="sm">
              <XCircle className="h-4 w-4 mr-1" />
              全部禁用
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">状态</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">类别</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">适用范围</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">期望值</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">来源</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">严重度</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-neutral-500 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200">
              {rules.map((rule) => (
                <>
                  <tr
                    key={rule.id}
                    className={cn('hover:bg-neutral-50 transition-colors', !rule.enabled && 'opacity-60')}
                  >
                    <td className="px-6 py-4">
                      <button
                        onClick={() => toggleRule(rule.id)}
                        className={cn(
                          'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                          rule.enabled ? 'bg-primary-600' : 'bg-neutral-300',
                        )}
                      >
                        <span
                          className={cn(
                            'inline-block h-3 w-3 transform rounded-full bg-white transition-transform',
                            rule.enabled ? 'translate-x-5' : 'translate-x-1',
                          )}
                        />
                      </button>
                    </td>
                    <td className="px-6 py-4 text-neutral-900 capitalize">{rule.category}</td>
                    <td className="px-6 py-4 text-neutral-700">{rule.target.selector}</td>
                    <td className="px-6 py-4 text-neutral-700">
                      {Object.entries(rule.expectation)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(', ')}
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-xs text-neutral-500">{rule.source.type === 'requirement_doc' ? '规范文档' : '手动输入'}</span>
                    </td>
                    <td className="px-6 py-4">
                      <SeverityBadge severity={rule.severity} />
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => setExpandedRule(expandedRule === rule.id ? null : rule.id)}
                        className="p-1 rounded-md hover:bg-neutral-200 text-neutral-400"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                  {expandedRule === rule.id && (
                    <tr>
                      <td colSpan={7} className="px-6 py-4 bg-neutral-50 border-t border-neutral-100">
                        <div className="space-y-2">
                          <p className="text-xs text-neutral-500">来源片段：</p>
                          <p className="text-sm text-neutral-700 bg-white border border-neutral-200 rounded-lg p-3">
                            {rule.source.excerpt || '无来源片段'}
                          </p>
                          {rule.source.location && (
                            <p className="text-xs text-neutral-400">位置：{rule.source.location}</p>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
