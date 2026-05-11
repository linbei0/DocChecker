import type { FormatRule, UnsupportedRequirement } from '@/entities/ruleset/model'

export type EditableValueKind = 'string' | 'number' | 'boolean' | 'list' | 'json'

export type ExpectationDraftField = {
  key: string
  value: string
  kind: EditableValueKind
}

export type ExpectationDraftPatch = Partial<ExpectationDraftField>

export function reasonCodeLabel(code: string) {
  return (
    {
      missing_checker: '缺少检查器',
      ambiguous_requirement: '语义不明确',
      out_of_scope: '超出范围',
      llm_not_configured: 'LLM 未配置',
      invalid_llm_response: 'LLM 响应无效',
      unsupported_field: '字段暂不支持',
    }[code] || code
  )
}

export function capabilityStatusLabel(status: string) {
  return (
    {
      auto_checkable: '可自动校验',
      needs_confirmation: '建议确认',
      unsupported: '当前不支持',
      conflict: '证据冲突',
      parse_error: '解析失败',
    }[status] || status
  )
}

export function evidenceTypeLabel(type: string) {
  return (
    {
      explicit_text: '文字规则',
      comment_anchor: '批注锚点',
      exemplar_format: '样例格式',
      style_cluster: '样式簇',
      table_cell: '表格单元格',
      llm_candidate: 'LLM 候选',
      manual_text: '手动文本',
      template: '模板',
    }[type] || type
  )
}

export function unsupportedActionHint(requirement: UnsupportedRequirement) {
  if (requirement.capability_status === 'conflict') {
    return '这类项通常对应同目标的冲突规则。请优先在"建议人工确认"筛选里确认最终可执行规则。'
  }
  if (requirement.capability_status === 'needs_confirmation') {
    return '这类项本身还没有形成可执行规则，不能直接启用，需要先补充更明确的规则表达。'
  }
  return '这类项当前没有对应检查器，暂时不能直接人工确认成自动检查规则。'
}

export function createExpectationDraft(expectation: Record<string, unknown>): ExpectationDraftField[] {
  return Object.entries(expectation).map(([key, value]) => ({
    key,
    value: draftValue(value),
    kind: inferValueKind(value),
  }))
}

export function serializeExpectationDraft(
  fields: ExpectationDraftField[],
): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  if (fields.length === 0) {
    return { ok: false, error: '至少保留一个期望字段。' }
  }

  const expectation: Record<string, unknown> = {}
  const seen = new Set<string>()
  for (const field of fields) {
    const key = field.key.trim()
    if (!key) return { ok: false, error: '期望值字段名称不能为空。' }
    if (seen.has(key)) return { ok: false, error: `期望值字段重复：${key}` }
    seen.add(key)

    const parsed = parseDraftValue(field)
    if (!parsed.ok) return parsed
    expectation[key] = parsed.value
  }
  return { ok: true, value: expectation }
}

export function parseDraftValue(
  field: ExpectationDraftField,
): { ok: true; value: unknown } | { ok: false; error: string } {
  if (field.kind === 'number') {
    const value = Number(field.value)
    if (!Number.isFinite(value)) {
      return { ok: false, error: `${fieldLabel(field.key)} 必须是有效数字。` }
    }
    return { ok: true, value }
  }
  if (field.kind === 'boolean') {
    return { ok: true, value: field.value === 'true' }
  }
  if (field.kind === 'list') {
    return {
      ok: true,
      value: field.value
        .split(/[,，、]/)
        .map((item) => item.trim())
        .filter(Boolean),
    }
  }
  if (field.kind === 'json') {
    try {
      return { ok: true, value: JSON.parse(field.value) as unknown }
    } catch {
      return { ok: false, error: `${fieldLabel(field.key)} 的复杂值格式不正确。` }
    }
  }
  return { ok: true, value: field.value }
}

export function inferValueKind(value: unknown): EditableValueKind {
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  if (Array.isArray(value)) return 'list'
  if (typeof value === 'object' && value !== null) return 'json'
  return 'string'
}

export function draftValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).join('，')
  if (typeof value === 'object' && value !== null) return JSON.stringify(value, null, 2)
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return value === null || value === undefined ? '' : String(value)
}

export function normalizeDraftKindChange(
  field: ExpectationDraftField,
  nextKind: EditableValueKind,
): ExpectationDraftPatch {
  if (nextKind === field.kind) return { kind: nextKind }
  if (nextKind === 'boolean') {
    return { kind: nextKind, value: field.value === 'false' ? 'false' : 'true' }
  }
  if (nextKind === 'number') {
    return { kind: nextKind, value: Number.isFinite(Number(field.value)) ? field.value : '' }
  }
  if (nextKind === 'json') {
    return { kind: nextKind, value: JSON.stringify(field.value, null, 2) }
  }
  return { kind: nextKind, value: field.value }
}

export function formatExpectationSummary(expectation: Record<string, unknown>) {
  const entries = Object.entries(expectation)
  if (entries.length === 0) return '未设置期望字段'
  return entries.map(([key, value]) => `${fieldLabel(key)}：${formatExpectationValue(key, value)}`).join('，')
}

export function formatExpectationValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '未填写'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.map((item) => formatExpectationValue(key, item)).join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  const unit = fieldUnit(key)
  return unit ? `${String(value)} ${unit}` : String(value)
}

export function fieldLabel(key: string) {
  return FIELD_META[key]?.label || key
}

export function fieldUnit(key: string) {
  return FIELD_META[key]?.unit
}

export function categoryLabel(category: string) {
  return CATEGORY_LABELS[category] || category
}

export function targetScopeLabel(scope: string) {
  return TARGET_SCOPE_LABELS[scope] || scope
}

export function formatRuleTarget(rule: FormatRule) {
  return [targetScopeLabel(rule.target.scope), rule.target.selector].filter(Boolean).join(' / ')
}

export function capabilityExplanation(rule: FormatRule) {
  const status = rule.capability_status || 'auto_checkable'
  if (status === 'auto_checkable') {
    return '该规则已匹配到现有检查器，启用后会自动检查并生成证据位置。'
  }
  if (status === 'needs_confirmation') {
    return rule.source.evidence_type === 'llm_candidate'
      ? '该规则来自 LLM 候选或置信度偏低，需要人工确认后再进入自动检查。'
      : '该规则字段可被系统处理，但目标范围或期望值仍需要人工确认。'
  }
  if (status === 'conflict') {
    return '系统识别到同一目标附近存在冲突表达，需要先确定最终采用哪条规则。'
  }
  if (status === 'parse_error') {
    return '系统解析这条规则时遇到错误，应回到原始规范文本定位问题后再发布。'
  }
  return '该规则当前不能进入自动检查，可导出为能力缺口并用于后续补检查器。'
}

const CATEGORY_LABELS: Record<string, string> = {
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

const TARGET_SCOPE_LABELS: Record<string, string> = {
  document: '全文',
  section: '章节',
  paragraph: '段落',
  'body.paragraph': '正文段落',
  heading: '标题',
  'heading.1': '一级标题',
  'heading.2': '二级标题',
  'heading.3': '三级标题',
  'heading.4': '四级标题',
  'heading.5': '五级标题',
  'heading.6': '六级标题',
  'cover.title': '论文题目',
  'abstract.paragraph': '摘要段落',
  'keywords.paragraph': '关键词段落',
  table_cell: '表格单元格',
  'table.cell': '表格单元格',
  'table.paragraph': '表格段落',
  table: '表格',
  header_footer: '页眉页脚',
  caption: '图表题注',
  reference: '参考文献',
  toc: '目录',
  abstract: '摘要',
  page: '页面',
  'document.page': '页面设置',
}

const FIELD_META: Record<string, { label: string; unit?: string }> = {
  fontFamilyEastAsia: { label: '中文字体' },
  fontFamilyAscii: { label: '英文字体' },
  fontSizePt: { label: '字号', unit: 'pt' },
  bold: { label: '加粗' },
  alignment: { label: '对齐方式' },
  firstLineIndentCm: { label: '首行缩进', unit: 'cm' },
  lineSpacing: { label: '行距' },
  spaceBeforePt: { label: '段前间距', unit: 'pt' },
  spaceAfterPt: { label: '段后间距', unit: 'pt' },
  textContains: { label: '必须包含文本' },
  requiresPageNumber: { label: '必须包含页码' },
  captionPattern: { label: '题注编号格式' },
  requiresTableCaption: { label: '表格题注' },
  requiresFigureCaption: { label: '图片题注' },
  tableCaptionPosition: { label: '表题位置' },
  figureCaptionPosition: { label: '图题位置' },
  referenceStyle: { label: '参考文献样式' },
  requiredSections: { label: '必要章节' },
  order: { label: '章节顺序' },
  autoGenerated: { label: '自动生成' },
  page_width_cm: { label: '页面宽度', unit: 'cm' },
  page_height_cm: { label: '页面高度', unit: 'cm' },
  margin_top_cm: { label: '上边距', unit: 'cm' },
  margin_bottom_cm: { label: '下边距', unit: 'cm' },
  margin_left_cm: { label: '左边距', unit: 'cm' },
  margin_right_cm: { label: '右边距', unit: 'cm' },
  header_distance_cm: { label: '页眉距边界', unit: 'cm' },
  footer_distance_cm: { label: '页脚距边界', unit: 'cm' },
}

export const FIELD_OPTIONS = Object.entries(FIELD_META).map(([key, value]) => ({
  key,
  label: value.label,
}))
