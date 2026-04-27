import { apiRequest } from '@/shared/api/client'
import { checkTaskSchema, type CheckTask } from '@/entities/task/model'

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
