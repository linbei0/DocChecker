export const queryKeys = {
  documents: {
    all: ['documents'] as const,
    detail: (id: string) => ['documents', id] as const,
  },
  rulesets: {
    all: ['rulesets'] as const,
    list: (limit: number, offset: number, includeHistory = false) =>
      ['rulesets', 'list', limit, offset, includeHistory] as const,
    detail: (id: string) => ['rulesets', id] as const,
    versions: (id: string) => ['rulesets', id, 'versions'] as const,
  },
  draftRulesets: {
    all: ['draft-rulesets'] as const,
    detail: (id: string) => ['draft-rulesets', id] as const,
  },
  checkTasks: {
    all: ['check-tasks'] as const,
    list: (limit: number, offset: number) => ['check-tasks', 'list', limit, offset] as const,
    detail: (id: string) => ['check-tasks', id] as const,
  },
  reports: {
    detail: (id: string) => ['reports', id] as const,
    export: (id: string, format: 'markdown') => ['reports', id, 'export', format] as const,
  },
}
