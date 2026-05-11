import { Trash2 } from 'lucide-react'
import type {
  EditableValueKind,
  ExpectationDraftField,
  ExpectationDraftPatch,
} from './ruleConfirmText'
import { FIELD_OPTIONS, fieldLabel, normalizeDraftKindChange } from './ruleConfirmText'

export function ExpectationEditor({
  fields,
  onFieldChange,
  onRemoveField,
}: {
  fields: ExpectationDraftField[]
  onFieldChange: (index: number, patch: ExpectationDraftPatch) => void
  onRemoveField: (index: number) => void
}) {
  if (fields.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-neutral-300 bg-white px-4 py-6 text-center text-sm text-neutral-500">
        当前没有期望字段。
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <datalist id="expectation-field-options">
        {FIELD_OPTIONS.map((field) => (
          <option key={field.key} value={field.key}>
            {field.label}
          </option>
        ))}
      </datalist>
      {fields.map((field, index) => (
        <div
          key={`${field.key || 'new'}-${index}`}
          className="rounded-xl border border-neutral-200 bg-white p-3 shadow-sm"
        >
          <div className="grid gap-3 lg:grid-cols-[1.2fr_8rem_1.4fr_auto]">
            <label className="min-w-0 space-y-1.5">
              <span className="text-[11px] font-medium text-neutral-500">字段</span>
              <input
                list="expectation-field-options"
                value={field.key}
                onChange={(event) => onFieldChange(index, { key: event.target.value })}
                className="h-9 w-full rounded-lg border border-neutral-200 px-3 text-sm text-neutral-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                placeholder="例如 fontSizePt"
              />
              {field.key && (
                <span className="block truncate text-[11px] text-neutral-400">
                  {fieldLabel(field.key)}
                </span>
              )}
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] font-medium text-neutral-500">类型</span>
              <select
                value={field.kind}
                onChange={(event) =>
                  onFieldChange(index, normalizeDraftKindChange(field, event.target.value as EditableValueKind))
                }
                className="h-9 w-full rounded-lg border border-neutral-200 bg-white px-2.5 text-sm text-neutral-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
              >
                <option value="string">文本</option>
                <option value="number">数字</option>
                <option value="boolean">是/否</option>
                <option value="list">列表</option>
                <option value="json">复杂值</option>
              </select>
            </label>
            <ExpectationValueInput
              field={field}
              onChange={(value) => onFieldChange(index, { value })}
            />
            <button
              type="button"
              onClick={() => onRemoveField(index)}
              className="inline-flex h-9 w-9 items-center justify-center self-end rounded-lg text-neutral-400 transition-colors hover:bg-danger-50 hover:text-danger-600"
              aria-label="删除期望字段"
              title="删除期望字段"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

function ExpectationValueInput({
  field,
  onChange,
}: {
  field: ExpectationDraftField
  onChange: (value: string) => void
}) {
  if (field.kind === 'boolean') {
    return (
      <label className="space-y-1.5">
        <span className="text-[11px] font-medium text-neutral-500">值</span>
        <select
          value={field.value}
          onChange={(event) => onChange(event.target.value)}
          className="h-9 w-full rounded-lg border border-neutral-200 bg-white px-2.5 text-sm text-neutral-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
        >
          <option value="true">是</option>
          <option value="false">否</option>
        </select>
      </label>
    )
  }

  if (field.kind === 'json') {
    return (
      <label className="space-y-1.5">
        <span className="text-[11px] font-medium text-neutral-500">复杂值</span>
        <textarea
          value={field.value}
          onChange={(event) => onChange(event.target.value)}
          rows={2}
          className="min-h-9 w-full rounded-lg border border-neutral-200 px-3 py-2 font-mono text-xs text-neutral-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
        />
      </label>
    )
  }

  return (
    <label className="space-y-1.5">
      <span className="text-[11px] font-medium text-neutral-500">
        {field.kind === 'list' ? '值，多个用逗号分隔' : '值'}
      </span>
      <input
        value={field.value}
        type={field.kind === 'number' ? 'number' : 'text'}
        step={field.kind === 'number' ? 'any' : undefined}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-full rounded-lg border border-neutral-200 px-3 text-sm text-neutral-900 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
      />
    </label>
  )
}
