import { useMutation, useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/shared/api/queryKeys'
import { createRuleSet, listRuleSets } from './api'

export function useRuleSetsQuery() {
  return useQuery({
    queryKey: queryKeys.rulesets.all,
    queryFn: listRuleSets,
  })
}

export function useCreateRuleSetMutation() {
  return useMutation({
    mutationFn: createRuleSet,
  })
}
