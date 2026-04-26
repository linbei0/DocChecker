import { apiUpload } from '@/shared/api/client'
import { uploadedDocumentSchema, type UploadedDocument } from '@/entities/document/model'

export async function uploadDocument(file: File): Promise<UploadedDocument> {
  const formData = new FormData()
  formData.append('file', file)
  return apiUpload('/api/documents', formData, uploadedDocumentSchema)
}
