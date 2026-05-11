import { Link } from 'react-router'
import { AlertCircle, ArrowLeft } from 'lucide-react'
import { Button } from '@/shared/ui/Button'

export function RuleConfirmLoading() {
  return (
    <div className="mx-auto flex max-w-7xl items-center justify-center px-4 py-20 text-sm text-neutral-500 sm:px-6 lg:px-8">
      <div className="flex items-center gap-3">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary-300 border-t-primary-600" />
        加载候选规则中...
      </div>
    </div>
  )
}

export function RuleConfirmMissing() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-20 text-center sm:px-6 lg:px-8">
      <div className="mx-auto max-w-md">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-neutral-100">
          <AlertCircle className="h-8 w-8 text-neutral-400" />
        </div>
        <h2 className="mt-6 text-lg font-semibold text-neutral-900">候选规则集不存在</h2>
        <p className="mt-2 text-sm text-neutral-500">该规则集可能已过期或已被删除。</p>
        <Link to="/checks/new" className="mt-6 inline-flex items-center text-sm font-medium text-primary-600 hover:text-primary-700">
          <ArrowLeft className="mr-1.5 h-4 w-4" />
          返回新建检查
        </Link>
      </div>
    </div>
  )
}

type DraftStatusStateProps = {
  message: string
  onBack: () => void
}

export function RuleConfirmProcessing({ message, onBack }: DraftStatusStateProps) {
  return (
    <DraftStatusShell
      title="正在生成候选规则"
      body="规范文档已经进入后台抽取流程。本页会自动刷新，生成完成后进入规则确认工作台。"
      message={message}
      onBack={onBack}
    />
  )
}

export function RuleConfirmFailed({ message, onBack }: DraftStatusStateProps) {
  return (
    <DraftStatusShell
      title="候选规则生成失败"
      body="后台抽取流程返回了明确错误，当前草稿不会进入发布步骤。"
      message={message}
      onBack={onBack}
      tone="danger"
    />
  )
}

type DraftStatusShellProps = DraftStatusStateProps & {
  title: string
  body: string
  tone?: 'neutral' | 'danger'
}

function DraftStatusShell({ title, body, message, onBack, tone = 'neutral' }: DraftStatusShellProps) {
  const isDanger = tone === 'danger'
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <div className={isDanger ? 'rounded-2xl border border-danger-100 bg-white p-8 shadow-sm' : 'rounded-2xl border border-neutral-200 bg-white p-8 shadow-sm'}>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
          <div className={isDanger ? 'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-danger-50' : 'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary-50'}>
            {isDanger ? (
              <AlertCircle className="h-6 w-6 text-danger-600" />
            ) : (
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-200 border-t-primary-600" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-semibold text-neutral-950">{title}</h1>
            <p className="mt-2 text-sm leading-relaxed text-neutral-600">{body}</p>
            <div className={isDanger ? 'mt-5 whitespace-pre-wrap break-words rounded-xl border border-danger-100 bg-danger-50 px-4 py-3 text-sm text-danger-700' : 'mt-5 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm text-neutral-600'}>
              {message}
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button variant="secondary" onClick={onBack}>
                <ArrowLeft className="mr-1.5 h-4 w-4" />
                返回新建检查
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
