import { useMutation } from '@tanstack/react-query'
import { uploadDocument, uploadRequirementDocument } from './api'

export function useUploadDocumentMutation() {
  return useMutation({
    mutationFn: uploadDocument,
  })
}

export function useUploadRequirementDocumentMutation() {
  return useMutation({
    mutationFn: uploadRequirementDocument,
  })
}
