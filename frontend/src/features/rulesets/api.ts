import { apiRequest } from '@/shared/api/client'
import {
  draftRuleSetSchema,
  ruleSetSchema,
  type DraftRuleSet,
  type FormatRule,
  type RuleSet,
} from '@/entities/ruleset/model'

export interface CreateDraftRuleSetRequest {
  document_id: string
  source_type: 'manual' | 'requirement_doc' | 'template'
  manual_text?: string
  requirement_document_id?: string
  template_ruleset_id?: string
}

export interface UpdateDraftRuleSetRequest {
  name?: string
  rules: FormatRule[]
  parse_warnings?: string[]
}

export async function createRuleSet(ruleset: RuleSet): Promise<RuleSet> {
  return apiRequest('/api/rulesets', ruleSetSchema, {
    method: 'POST',
    body: JSON.stringify(ruleset),
  })
}

export async function listRuleSets(): Promise<RuleSet[]> {
  const schema = ruleSetSchema.array()
  return apiRequest('/api/rulesets', schema)
}

export async function createDraftRuleSet(
  request: CreateDraftRuleSetRequest,
): Promise<DraftRuleSet> {
  return apiRequest('/api/draft-rulesets', draftRuleSetSchema, {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function getDraftRuleSet(draftId: string): Promise<DraftRuleSet> {
  return apiRequest(`/api/draft-rulesets/${draftId}`, draftRuleSetSchema)
}

export async function updateDraftRuleSet(
  draftId: string,
  request: UpdateDraftRuleSetRequest,
): Promise<DraftRuleSet> {
  return apiRequest(`/api/draft-rulesets/${draftId}`, draftRuleSetSchema, {
    method: 'PATCH',
    body: JSON.stringify(request),
  })
}

export async function publishDraftRuleSet(draftId: string): Promise<RuleSet> {
  return apiRequest(`/api/draft-rulesets/${draftId}/publish`, ruleSetSchema, {
    method: 'POST',
  })
}
