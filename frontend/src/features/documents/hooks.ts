import { useMutation } from '@tanstack/react-query'
import { uploadDocument } from './api'

export function useUploadDocumentMutation() {
  return useMutation({
    mutationFn: uploadDocument,
  })
}
