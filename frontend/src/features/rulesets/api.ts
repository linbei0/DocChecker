import { apiRequest } from '@/shared/api/client'
import { ruleSetSchema, type RuleSet } from '@/entities/ruleset/model'

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
