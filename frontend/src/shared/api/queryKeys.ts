export const queryKeys = {
  documents: {
    all: ['documents'] as const,
    detail: (id: string) => ['documents', id] as const,
  },
  rulesets: {
    all: ['rulesets'] as const,
    detail: (id: string) => ['rulesets', id] as const,
  },
  reports: {
    detail: (id: string) => ['reports', id] as const,
    export: (id: string, format: 'markdown') => ['reports', id, 'export', format] as const,
  },
}
