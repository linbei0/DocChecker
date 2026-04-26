import { createBrowserRouter } from 'react-router'
import { AppShell } from './AppShell'
import { CheckNewPage } from '@/pages/check-new/CheckNewPage'
import { RuleConfirmPage } from '@/pages/rule-confirm/RuleConfirmPage'
import { ReportDetailPage } from '@/pages/report-detail/ReportDetailPage'
import { TemplatesPage } from '@/pages/templates/TemplatesPage'
import { HistoryPage } from '@/pages/history/HistoryPage'
import { RouteErrorPage } from '@/pages/route-error/RouteErrorPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <CheckNewPage /> },
      { path: 'checks/new', element: <CheckNewPage /> },
      { path: 'checks/:taskId/rules', element: <RuleConfirmPage /> },
      { path: 'reports/:reportId', element: <ReportDetailPage /> },
      { path: 'templates', element: <TemplatesPage /> },
      { path: 'history', element: <HistoryPage /> },
      { path: '*', element: <RouteErrorPage /> },
    ],
  },
])
