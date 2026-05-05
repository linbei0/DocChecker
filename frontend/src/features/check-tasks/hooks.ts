import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/shared/api/queryKeys'
import { createCheckTask, deleteCheckTask, getCheckTask, listCheckTasks } from './api'

interface CheckTaskListOptions {
  limit?: number
  offset?: number
}

export function useCreateCheckTaskMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createCheckTask,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.checkTasks.all })
    },
  })
}

export function useCheckTaskQuery(taskId: string) {
  return useQuery({
    queryKey: queryKeys.checkTasks.detail(taskId),
    queryFn: () => getCheckTask(taskId),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'running' ? 2000 : false
    },
  })
}

export function useCheckTasksQuery({ limit = 50, offset = 0 }: CheckTaskListOptions = {}) {
  return useQuery({
    queryKey: queryKeys.checkTasks.list(limit, offset),
    queryFn: () => listCheckTasks(limit, offset),
  })
}

export function useDeleteCheckTaskMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteCheckTask,
    onSuccess: (_data, taskId) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.checkTasks.all })
      void queryClient.removeQueries({ queryKey: queryKeys.checkTasks.detail(taskId) })
    },
  })
}
