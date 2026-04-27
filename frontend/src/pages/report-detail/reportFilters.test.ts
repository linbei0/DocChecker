import { describe, expect, it } from 'vitest'
import type { CheckFinding } from '@/entities/finding/model'
import { filterFindings } from './reportFilters'

function finding(
  id: string,
  severity: CheckFinding['severity'],
  category: string,
): CheckFinding {
  return {
    id,
    rule_id: id,
    checker_id: 'checker',
    category,
    severity,
    location: {},
    expected: {},
    actual: {},
    evidence: '',
    suggestion: '',
    certainty: 'certain',
  }
}

describe('filterFindings', () => {
  const findings = [
    finding('major-heading', 'major', 'heading'),
    finding('minor-font', 'minor', 'font'),
    finding('info-page', 'info', 'page'),
  ]

  it('filters by severity', () => {
    expect(filterFindings(findings, 'minor', 'all').map((item) => item.id)).toEqual([
      'minor-font',
    ])
  })

  it('filters by category', () => {
    expect(filterFindings(findings, 'all', 'heading').map((item) => item.id)).toEqual([
      'major-heading',
    ])
  })

  it('combines severity and category filters', () => {
    expect(filterFindings(findings, 'minor', 'heading')).toEqual([])
    expect(filterFindings(findings, 'major', 'heading').map((item) => item.id)).toEqual([
      'major-heading',
    ])
  })

  it('treats blocker findings as major for the simplified severity UI', () => {
    const blockerFinding = finding('blocker-page', 'blocker', 'page')

    expect(filterFindings([blockerFinding], 'major', 'all').map((item) => item.id)).toEqual([
      'blocker-page',
    ])
    expect(filterFindings([blockerFinding], 'info', 'all')).toEqual([])
  })
})
