import { z } from 'zod'

const ruleExtractionReasonCodeSchema = z.enum([
  'missing_checker',
  'ambiguous_requirement',
  'out_of_scope',
  'llm_not_configured',
  'invalid_llm_response',
  'unsupported_field',
])

export const formatRuleSchema = z.object({
  id: z.string(),
  category: z.string(),
  target: z.object({
    scope: z.string(),
    selector: z.string().nullish(),
  }),
  expectation: z.record(z.string(), z.unknown()),
  tolerance: z.record(z.string(), z.unknown()).optional(),
  severity: z.enum(['blocker', 'major', 'minor', 'info']),
  source: z.object({
    type: z.enum(['manual', 'requirement_doc', 'template']),
    excerpt: z.string(),
    location: z.string().nullish(),
    evidence_type: z
      .enum([
        'explicit_text',
        'comment_anchor',
        'exemplar_format',
        'style_cluster',
        'table_cell',
        'llm_candidate',
        'manual_text',
        'template',
      ])
      .optional(),
    evidence_label: z.string().nullish(),
  }),
  confidence: z.number().min(0).max(1).optional(),
  enabled: z.boolean().optional(),
  capability_status: z
    .enum(['auto_checkable', 'needs_confirmation', 'unsupported', 'conflict', 'parse_error'])
    .optional(),
  confirmation_required: z.boolean().optional(),
})

export const extractionSummarySchema = z.object({
  total_requirements: z.number(),
  structured_rules: z.number(),
  unsupported_requirements: z.number(),
  low_confidence_rules: z.number(),
  supported_categories: z.array(z.string()),
  unsupported_categories: z.array(z.string()),
  uncovered_categories: z.array(z.string()),
  auto_checkable_rules: z.number().optional(),
  needs_confirmation_rules: z.number().optional(),
  conflict_requirements: z.number().optional(),
  coverage_rate: z.number().optional(),
})

export const unsupportedRequirementSchema = z.object({
  category: z.string(),
  excerpt: z.string(),
  location: z.string().nullish(),
  reason: z.string(),
  reason_code: ruleExtractionReasonCodeSchema.optional(),
  target_scope: z.string().nullish(),
  capability_status: z
    .enum(['auto_checkable', 'needs_confirmation', 'unsupported', 'conflict', 'parse_error'])
    .optional(),
})

export const extractedRuleCandidateSchema = z.object({
  category: z.string(),
  target_scope: z.string(),
  selector: z.string().nullish(),
  expectation: z.record(z.string(), z.unknown()),
  evidence_span: z.string(),
  location: z.string().nullish(),
  checkability: z.enum(['checkable', 'needs_confirmation', 'unsupported']),
  confidence: z.number().min(0).max(1),
  reason: z.string().nullish(),
  evidence_type: z
    .enum([
      'explicit_text',
      'comment_anchor',
      'exemplar_format',
      'style_cluster',
      'table_cell',
      'llm_candidate',
      'manual_text',
      'template',
    ])
    .optional(),
})

export const ruleExtractionIssueSchema = z.object({
  location: z.string().nullish(),
  category: z.string().nullish(),
  reason_code: ruleExtractionReasonCodeSchema,
  message: z.string(),
  excerpt: z.string().nullish(),
})

export const ruleExtractionTraceSchema = z.object({
  mode: z.string(),
  candidates: z.array(extractedRuleCandidateSchema).optional(),
  issues: z.array(ruleExtractionIssueSchema).optional(),
})

export const ruleSetSchema = z.object({
  id: z.string(),
  name: z.string(),
  source_type: z.enum(['manual', 'requirement_doc', 'template']),
  version: z.string(),
  locale: z.string().optional(),
  rules: z.array(formatRuleSchema),
  created_at: z.string(),
})

export const draftRuleSetSchema = z.object({
  id: z.string(),
  name: z.string(),
  document_id: z.string(),
  source_type: z.enum(['manual', 'requirement_doc', 'template']),
  version: z.string(),
  locale: z.string().optional(),
  rules: z.array(formatRuleSchema),
  suggested_rules: z.array(formatRuleSchema).optional(),
  parse_warnings: z.array(z.string()),
  extraction_summary: extractionSummarySchema.optional(),
  unsupported_requirements: z.array(unsupportedRequirementSchema).optional(),
  extraction_trace: ruleExtractionTraceSchema.nullish(),
  status: z.enum(['draft', 'published']),
  published_ruleset_id: z.string().nullish(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type FormatRule = z.infer<typeof formatRuleSchema>
export type ExtractionSummary = z.infer<typeof extractionSummarySchema>
export type UnsupportedRequirement = z.infer<typeof unsupportedRequirementSchema>
export type ExtractedRuleCandidate = z.infer<typeof extractedRuleCandidateSchema>
export type RuleExtractionIssue = z.infer<typeof ruleExtractionIssueSchema>
export type RuleExtractionTrace = z.infer<typeof ruleExtractionTraceSchema>
export type RuleSet = z.infer<typeof ruleSetSchema>
export type DraftRuleSet = z.infer<typeof draftRuleSetSchema>
