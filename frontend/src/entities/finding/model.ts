import { z } from 'zod'

export const checkFindingSchema = z.object({
  id: z.string(),
  rule_id: z.string(),
  checker_id: z.string().optional(),
  category: z.string().nullish(),
  severity: z.enum(['blocker', 'major', 'minor', 'info']),
  location: z.object({
    section_path: z.string().nullish(),
    paragraph_index: z.number().nullish(),
    table_index: z.number().nullish(),
    row_index: z.number().nullish(),
    column_index: z.number().nullish(),
    area: z.string().nullish(),
    xml_path: z.string().nullish(),
  }),
  expected: z.record(z.string(), z.unknown()),
  actual: z.record(z.string(), z.unknown()),
  evidence: z.string(),
  suggestion: z.string(),
  certainty: z.enum(['certain', 'probable', 'unknown']).optional(),
})

export const checkReportSchema = z.object({
  id: z.string(),
  document_id: z.string(),
  ruleset_id: z.string(),
  checker_version: z.string().optional(),
  generated_at: z.string().optional(),
  findings: z.array(checkFindingSchema),
  parse_warnings: z.array(z.string()).optional(),
})

export type CheckFinding = z.infer<typeof checkFindingSchema>
export type CheckReport = z.infer<typeof checkReportSchema>
