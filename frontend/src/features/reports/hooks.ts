import { useMutation, useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/shared/api/queryKeys'
import { getReport, exportReport } from './api'

export function useReportQuery(reportId: string) {
  return useQuery({
    queryKey: queryKeys.reports.detail(reportId),
    queryFn: () => getReport(reportId),
    enabled: !!reportId,
  })
}

export function useExportReportMutation() {
  return useMutation({
    mutationFn: exportReport,
  })
}
