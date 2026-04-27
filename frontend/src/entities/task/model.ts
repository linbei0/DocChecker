import { z } from 'zod'

export const checkTaskSchema = z.object({
  id: z.string(),
  document_id: z.string(),
  ruleset_id: z.string(),
  status: z.enum(['pending', 'running', 'succeeded', 'failed']),
  report_id: z.string().nullish(),
  error: z.string().nullish(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type CheckTask = z.infer<typeof checkTaskSchema>
