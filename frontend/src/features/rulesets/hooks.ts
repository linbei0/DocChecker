import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/shared/api/queryKeys'
import {
  createDraftRuleSet,
  createRuleSet,
  deleteRuleSet,
  getDraftRuleSet,
  listRuleSetVersions,
  listRuleSets,
  type PublishDraftRuleSetRequest,
  publishDraftRuleSet,
  updateRuleSet,
  updateDraftRuleSet,
} from './api'

interface RuleSetListOptions {
  limit?: number
  offset?: number
  includeHistory?: boolean
}

interface PublishDraftRuleSetVariables {
  draftId: string
  request?: PublishDraftRuleSetRequest
}

export function useRuleSetsQuery({
  limit = 50,
  offset = 0,
  includeHistory = false,
}: RuleSetListOptions = {}) {
  return useQuery({
    queryKey: queryKeys.rulesets.list(limit, offset, includeHistory),
    queryFn: () => listRuleSets(limit, offset, includeHistory),
  })
}

export function useRuleSetVersionsQuery(rulesetId: string) {
  return useQuery({
    queryKey: queryKeys.rulesets.versions(rulesetId),
    queryFn: () => listRuleSetVersions(rulesetId),
    enabled: !!rulesetId,
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

export function useUpdateRuleSetMutation(rulesetId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateRuleSet.bind(null, rulesetId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.rulesets.all })
      void queryClient.invalidateQueries({ queryKey: queryKeys.rulesets.detail(rulesetId) })
    },
  })
}

export function useDeleteRuleSetMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteRuleSet,
    onSuccess: (_data, rulesetId) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.rulesets.all })
      void queryClient.removeQueries({ queryKey: queryKeys.rulesets.detail(rulesetId) })
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
    refetchInterval: (query) => (query.state.data?.status === 'processing' ? 1500 : false),
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
    mutationFn: ({ draftId, request }: PublishDraftRuleSetVariables) =>
      publishDraftRuleSet(draftId, request),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.rulesets.all })
    },
  })
}
