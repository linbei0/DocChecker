import { apiRequest } from '@/shared/api/client'
import { z } from 'zod'
import { checkTaskSchema, type CheckTask } from '@/entities/task/model'

const deleteResponseSchema = z.object({
  id: z.string(),
  deleted: z.boolean(),
})

export interface CreateCheckTaskRequest {
  document_id: string
  ruleset_id: string
}

export async function createCheckTask(request: CreateCheckTaskRequest): Promise<CheckTask> {
  return apiRequest('/api/check-tasks', checkTaskSchema, {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function getCheckTask(taskId: string): Promise<CheckTask> {
  return apiRequest(`/api/check-tasks/${taskId}`, checkTaskSchema)
}

export async function listCheckTasks(): Promise<CheckTask[]> {
  return apiRequest('/api/check-tasks', checkTaskSchema.array())
}

export async function deleteCheckTask(taskId: string): Promise<void> {
  await apiRequest(`/api/check-tasks/${taskId}`, deleteResponseSchema, {
    method: 'DELETE',
  })
}
