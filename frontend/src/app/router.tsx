import { createBrowserRouter, type RouteObject } from 'react-router'
import { AppShell } from './AppShell'
import { RouteErrorPage } from '@/pages/route-error/RouteErrorPage'

const checkNewRoute = async () => ({
  Component: (await import('@/pages/check-new/CheckNewPage')).CheckNewPage,
})

const ruleConfirmRoute = async () => ({
  Component: (await import('@/pages/rule-confirm/RuleConfirmPage')).RuleConfirmPage,
})

const checkProgressRoute = async () => ({
  Component: (await import('@/pages/check-progress/CheckProgressPage')).CheckProgressPage,
})

const reportDetailRoute = async () => ({
  Component: (await import('@/pages/report-detail/ReportDetailPage')).ReportDetailPage,
})

const templatesRoute = async () => ({
  Component: (await import('@/pages/templates/TemplatesPage')).TemplatesPage,
})

const historyRoute = async () => ({
  Component: (await import('@/pages/history/HistoryPage')).HistoryPage,
})

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, lazy: checkNewRoute },
      { path: 'checks/new', lazy: checkNewRoute },
      { path: 'checks/:taskId/rules', lazy: ruleConfirmRoute },
      { path: 'checks/:taskId/progress', lazy: checkProgressRoute },
      { path: 'reports/:reportId', lazy: reportDetailRoute },
      { path: 'templates', lazy: templatesRoute },
      { path: 'history', lazy: historyRoute },
      { path: '*', element: <RouteErrorPage /> },
    ],
  },
] satisfies RouteObject[])
