import { describe, expect, it } from 'vitest'
import type {
  FormatRule,
  RuleExtractionTrace,
  UnsupportedRequirement,
} from '@/entities/ruleset/model'
import {
  buildFeedbackGroups,
  buildTraceDiagnosis,
  buildUnsupportedBacklogPayload,
} from './ruleReviewDiagnostics'

function rule(
  id: string,
  capabilityStatus: FormatRule['capability_status'],
  evidenceType: FormatRule['source']['evidence_type'],
): FormatRule {
  return {
    id,
    category: 'font',
    target: { scope: 'body.paragraph' },
    expectation: { fontSizePt: 12 },
    severity: 'major',
    source: {
      type: 'requirement_doc',
      excerpt: `${id} excerpt`,
      location: `comment:${id}`,
      evidence_type: evidenceType,
    },
    confidence: 0.7,
    enabled: false,
    capability_status: capabilityStatus,
    confirmation_required: capabilityStatus !== 'auto_checkable',
  }
}

function unsupported(
  reasonCode: UnsupportedRequirement['reason_code'],
  capabilityStatus: UnsupportedRequirement['capability_status'],
): UnsupportedRequirement {
  return {
    category: 'caption',
    excerpt: `${reasonCode} excerpt`,
    location: `paragraph:${reasonCode}`,
    reason: `${reasonCode} reason`,
    reason_code: reasonCode,
    capability_status: capabilityStatus,
  }
}

describe('rule review diagnostics', () => {
  it('groups review items by user-facing reason', () => {
    const groups = buildFeedbackGroups(
      [
        rule('llm', 'needs_confirmation', 'llm_candidate'),
        rule('scope', 'needs_confirmation', 'comment_anchor'),
        rule('conflict', 'conflict', 'explicit_text'),
      ],
      [
        unsupported('unsupported_field', 'unsupported'),
        unsupported('invalid_llm_response', 'unsupported'),
      ],
    )

    expect(groups.find((item) => item.id === 'llm')?.count).toBe(2)
    expect(groups.find((item) => item.id === 'conflict')?.count).toBe(1)
    expect(groups.find((item) => item.id === 'unsupported')?.count).toBe(1)
    expect(groups.find((item) => item.id === 'scope')?.count).toBe(1)
  })

  it('builds trace diagnosis and exports grouped backlog metadata', () => {
    const trace: RuleExtractionTrace = {
      mode: 'hybrid',
      stats: {
        local_candidate_count: 1,
        llm_candidate_count: 1,
        llm_rejected_count: 1,
        unsupported_field_count: 2,
        conflict_count: 1,
        auto_checkable_candidate_count: 1,
        needs_confirmation_candidate_count: 1,
        unsupported_candidate_count: 1,
        auto_checkable_conversion_rate: 0.25,
      },
    }

    const diagnosis = buildTraceDiagnosis(trace)
    const payload = buildUnsupportedBacklogPayload({
      draftId: 'draft_1',
      generatedAt: '2026-05-04T00:00:00+08:00',
      rules: [rule('llm', 'needs_confirmation', 'llm_candidate')],
      unsupportedRequirements: [unsupported('unsupported_field', 'unsupported')],
      extractionTrace: trace,
    })

    expect(diagnosis).toHaveLength(4)
    expect(payload.summary.feedback_groups).toEqual(
      expect.arrayContaining([expect.objectContaining({ id: 'unsupported', count: 1 })]),
    )
    expect(payload.summary.trace_diagnosis).toEqual(diagnosis)
  })
})
