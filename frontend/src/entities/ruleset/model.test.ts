import { describe, expect, it } from 'vitest'
import { draftRuleSetSchema } from './model'

describe('draftRuleSetSchema', () => {
  it('validates draft rulesets returned by the backend', () => {
    const result = draftRuleSetSchema.safeParse({
      id: 'draft_1',
      name: '候选规则集',
      document_id: 'doc_1',
      source_type: 'manual',
      version: '1.0.0',
      locale: 'zh-CN',
      rules: [],
      parse_warnings: ['未识别到明确规则'],
      status: 'draft',
      published_ruleset_id: null,
      created_at: '2026-04-27T00:00:00+08:00',
      updated_at: '2026-04-27T00:00:00+08:00',
    })

    expect(result.success).toBe(true)
  })
})
