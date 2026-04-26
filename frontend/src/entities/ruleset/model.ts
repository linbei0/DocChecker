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

export const ruleSetSchema = z.object({
  id: z.string(),
  name: z.string(),
  source_type: z.enum(['manual', 'requirement_doc', 'template']),
  version: z.string(),
  locale: z.string().optional(),
  rules: z.array(formatRuleSchema),
  created_at: z.string(),
})

export type FormatRule = z.infer<typeof formatRuleSchema>
export type RuleSet = z.infer<typeof ruleSetSchema>
