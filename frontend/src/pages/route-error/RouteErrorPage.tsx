import { isRouteErrorResponse, Link, useRouteError } from 'react-router'
import { AlertCircle, ArrowLeft } from 'lucide-react'

export function RouteErrorPage() {
  const error = useRouteError()
  const title = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : '页面出错'
  const message = isRouteErrorResponse(error)
    ? '当前地址没有匹配的页面，或页面资源不可用。'
    : error instanceof Error
      ? error.message
      : '发生了未知错误。'

  return (
    <div className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-3xl flex-col items-center justify-center px-4 py-16 text-center">
      <AlertCircle className="h-12 w-12 text-warning-500" />
      <h1 className="mt-5 text-xl font-semibold text-neutral-900">{title}</h1>
      <p className="mt-2 text-sm text-neutral-500">{message}</p>
      <Link
        to="/checks/new"
        className="mt-6 inline-flex h-10 items-center justify-center rounded-lg bg-primary-600 px-4 text-sm font-medium text-white transition-colors hover:bg-primary-700"
      >
        <ArrowLeft className="mr-1.5 h-4 w-4" />
        返回新建检查
      </Link>
    </div>
  )
}
