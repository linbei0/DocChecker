import { apiRequest } from '@/shared/api/client'
import { checkReportSchema, type CheckReport } from '@/entities/finding/model'

export interface CreateCheckTaskRequest {
  document_id: string
  ruleset_id: string
}

export async function createCheckTask(request: CreateCheckTaskRequest): Promise<CheckReport> {
  return apiRequest('/api/check-tasks', checkReportSchema, {
    method: 'POST',
    body: JSON.stringify(request),
  })
}
