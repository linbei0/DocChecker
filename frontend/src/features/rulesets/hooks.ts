import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/shared/api/queryKeys'
import {
  createDraftRuleSet,
  createRuleSet,
  getDraftRuleSet,
  listRuleSets,
  publishDraftRuleSet,
  updateDraftRuleSet,
} from './api'

export function useRuleSetsQuery() {
  return useQuery({
    queryKey: queryKeys.rulesets.all,
    queryFn: listRuleSets,
  })
}

export function useCreateRuleSetMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createRuleSet,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.rulesets.all })
    },
  })
}

export function useCreateDraftRuleSetMutation() {
  return useMutation({
    mutationFn: createDraftRuleSet,
  })
}

export function useDraftRuleSetQuery(draftId: string) {
  return useQuery({
    queryKey: queryKeys.draftRulesets.detail(draftId),
    queryFn: () => getDraftRuleSet(draftId),
    enabled: !!draftId,
  })
}

export function useUpdateDraftRuleSetMutation(draftId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateDraftRuleSet.bind(null, draftId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.draftRulesets.detail(draftId) })
    },
  })
}

export function usePublishDraftRuleSetMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: publishDraftRuleSet,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.rulesets.all })
    },
  })
}
