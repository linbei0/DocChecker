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
      extraction_summary: {
        total_requirements: 2,
        structured_rules: 1,
        unsupported_requirements: 1,
        low_confidence_rules: 0,
        supported_categories: ['font'],
        unsupported_categories: ['reference'],
        uncovered_categories: ['page'],
      },
      unsupported_requirements: [
        {
          category: 'reference',
          excerpt: '参考文献按学校规范著录。',
          location: 'paragraph:4',
          reason: '当前缺少对应检查器。',
        },
        {
          category: 'heading',
          excerpt: '一级标题序号和标题之间空1格。',
          location: 'paragraph:5',
          reason: '规则候选包含当前检查器不支持的字段：spaceBetweenNumberAndTitle',
          reason_code: 'unsupported_field',
        },
      ],
      extraction_trace: {
        mode: 'hybrid',
        candidates: [],
        issues: [
          {
            location: 'paragraph:5',
            category: 'heading',
            reason_code: 'unsupported_field',
            message: '规则候选包含当前检查器不支持的字段：spaceBetweenNumberAndTitle',
            excerpt: '一级标题序号和标题之间空1格。',
          },
        ],
        stats: {
          processed_block_count: 81,
          batch_count: 2,
          local_candidate_count: 1,
          llm_candidate_count: 2,
          llm_rejected_count: 1,
          rejected_candidate_count: 1,
          unsupported_field_count: 1,
          conflict_count: 0,
          auto_checkable_candidate_count: 1,
          needs_confirmation_candidate_count: 1,
          unsupported_candidate_count: 1,
          auto_checkable_conversion_rate: 0.33,
        },
      },
      status: 'draft',
      published_ruleset_id: null,
      created_at: '2026-04-27T00:00:00+08:00',
      updated_at: '2026-04-27T00:00:00+08:00',
    })

    expect(result.success).toBe(true)
  })
})
