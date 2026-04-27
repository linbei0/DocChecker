import { z } from 'zod'

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
  }),
  confidence: z.number().min(0).max(1).optional(),
  enabled: z.boolean().optional(),
})

export const extractionSummarySchema = z.object({
  total_requirements: z.number(),
  structured_rules: z.number(),
  unsupported_requirements: z.number(),
  low_confidence_rules: z.number(),
  supported_categories: z.array(z.string()),
  unsupported_categories: z.array(z.string()),
  uncovered_categories: z.array(z.string()),
})

export const unsupportedRequirementSchema = z.object({
  category: z.string(),
  excerpt: z.string(),
  location: z.string().nullish(),
  reason: z.string(),
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
  parse_warnings: z.array(z.string()),
  extraction_summary: extractionSummarySchema.optional(),
  unsupported_requirements: z.array(unsupportedRequirementSchema).optional(),
  status: z.enum(['draft', 'published']),
  published_ruleset_id: z.string().nullish(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type FormatRule = z.infer<typeof formatRuleSchema>
export type ExtractionSummary = z.infer<typeof extractionSummarySchema>
export type UnsupportedRequirement = z.infer<typeof unsupportedRequirementSchema>
export type RuleSet = z.infer<typeof ruleSetSchema>
export type DraftRuleSet = z.infer<typeof draftRuleSetSchema>
