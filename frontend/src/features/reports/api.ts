import { apiRequest } from '@/shared/api/client'
import { checkReportSchema, type CheckReport } from '@/entities/finding/model'
import { z } from 'zod'

export async function getReport(reportId: string): Promise<CheckReport> {
  return apiRequest(`/api/reports/${reportId}`, checkReportSchema)
}

export const exportReportSchema = z.object({
  format: z.string(),
  path: z.string(),
  content: z.string(),
})

export type ExportReportResult = z.infer<typeof exportReportSchema>

export async function exportReport(reportId: string): Promise<ExportReportResult> {
  return apiRequest(`/api/reports/${reportId}/export`, exportReportSchema)
}
