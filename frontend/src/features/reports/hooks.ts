import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/shared/api/queryKeys'
import { getReport, exportReport } from './api'

export function useReportQuery(reportId: string) {
  return useQuery({
    queryKey: queryKeys.reports.detail(reportId),
    queryFn: () => getReport(reportId),
    enabled: !!reportId,
  })
}

export function useExportReportQuery(reportId: string) {
  return useQuery({
    queryKey: queryKeys.reports.export(reportId, 'markdown'),
    queryFn: () => exportReport(reportId),
    enabled: !!reportId,
  })
}
