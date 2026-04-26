import { Outlet, Link, useLocation } from 'react-router'
import { FileCheck, ClipboardList, History } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

const navItems = [
  { to: '/checks/new', label: '新建检查', icon: FileCheck },
  { to: '/templates', label: '规则模板', icon: ClipboardList },
  { to: '/history', label: '历史任务', icon: History },
]

export function AppShell() {
  const location = useLocation()

  return (
    <div className="min-h-screen flex flex-col bg-neutral-50">
      <header className="sticky top-0 z-50 bg-white border-b border-neutral-200">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600 text-white">
                <FileCheck className="h-5 w-5" />
              </div>
              <span className="text-lg font-semibold text-neutral-900">DocChecker</span>
              <span className="text-xs text-neutral-400 hidden sm:inline">论文格式检查</span>
            </div>
            <nav className="flex items-center gap-1">
              {navItems.map((item) => {
                const isActive = location.pathname.startsWith(item.to)
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={cn(
                      'flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900',
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                    <span className="hidden sm:inline">{item.label}</span>
                  </Link>
                )
              })}
            </nav>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-neutral-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4 text-center text-xs text-neutral-400">
          DocChecker 论文格式检查 v0.1.0
        </div>
      </footer>
    </div>
  )
}
