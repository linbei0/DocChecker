import { z } from 'zod'

export const uploadedDocumentSchema = z.object({
  document_id: z.string(),
  filename: z.string(),
  size_bytes: z.number(),
})

export const requirementBlockSchema = z.object({
  id: z.string(),
  type: z.enum(['paragraph', 'table', 'comment', 'header', 'footer']),
  location: z.string(),
  text: z.string(),
  style_name: z.string().nullish(),
  heading_path: z.array(z.string()).optional(),
  table_index: z.number().nullish(),
  row_index: z.number().nullish(),
  column_count: z.number().nullish(),
  cells: z.array(z.string()).optional(),
  context: z.record(z.string(), z.unknown()).optional(),
})

export const requirementDocumentSchema = z.object({
  id: z.string(),
  filename: z.string(),
  path: z.string(),
  size_bytes: z.number(),
  extracted_text: z.string(),
  blocks: z.array(requirementBlockSchema).optional(),
  created_at: z.string(),
})

export type UploadedDocument = z.infer<typeof uploadedDocumentSchema>
export type RequirementBlock = z.infer<typeof requirementBlockSchema>
export type RequirementDocument = z.infer<typeof requirementDocumentSchema>
