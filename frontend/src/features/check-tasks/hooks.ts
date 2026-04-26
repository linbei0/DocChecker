import { useMutation } from '@tanstack/react-query'
import { createCheckTask } from './api'

export function useCreateCheckTaskMutation() {
  return useMutation({
    mutationFn: createCheckTask,
  })
}
