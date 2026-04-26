import { z } from 'zod'

export const uploadedDocumentSchema = z.object({
  document_id: z.string(),
  filename: z.string(),
  size_bytes: z.number(),
})

export type UploadedDocument = z.infer<typeof uploadedDocumentSchema>
