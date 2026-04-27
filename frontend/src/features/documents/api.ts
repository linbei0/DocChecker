import { apiUpload } from '@/shared/api/client'
import {
  requirementDocumentSchema,
  uploadedDocumentSchema,
  type RequirementDocument,
  type UploadedDocument,
} from '@/entities/document/model'

export async function uploadDocument(file: File): Promise<UploadedDocument> {
  const formData = new FormData()
  formData.append('file', file)
  return apiUpload('/api/documents', formData, uploadedDocumentSchema)
}

export async function uploadRequirementDocument(file: File): Promise<RequirementDocument> {
  const formData = new FormData()
  formData.append('file', file)
  return apiUpload('/api/requirement-documents', formData, requirementDocumentSchema)
}
