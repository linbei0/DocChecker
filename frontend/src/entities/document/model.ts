import { z } from 'zod'

export const uploadedDocumentSchema = z.object({
  document_id: z.string(),
  filename: z.string(),
  size_bytes: z.number(),
})

export const requirementDocumentSchema = z.object({
  id: z.string(),
  filename: z.string(),
  path: z.string(),
  size_bytes: z.number(),
  extracted_text: z.string(),
  created_at: z.string(),
})

export type UploadedDocument = z.infer<typeof uploadedDocumentSchema>
export type RequirementDocument = z.infer<typeof requirementDocumentSchema>
