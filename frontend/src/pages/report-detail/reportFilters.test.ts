import { describe, expect, it } from 'vitest'
import type { CheckFinding } from '@/entities/finding/model'
import { filterFindings, groupFindingsByFragment } from './reportFilters'

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
    excerpt: `${id} 原文`,
    context: {
      field_label: '字号',
      style_name: '正文',
    },
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

  it('groups findings by readable fragment location', () => {
    const first = finding('font-1', 'major', 'font')
    first.location = { display_path: '绪论 / 第 3 段', paragraph_number: 3 }
    const second = finding('paragraph-1', 'minor', 'paragraph')
    second.location = { display_path: '绪论 / 第 3 段', paragraph_number: 3 }
    const third = finding('font-2', 'major', 'font')
    third.location = { paragraph_index: 9 }

    const groups = groupFindingsByFragment([first, second, third])

    expect(groups).toHaveLength(2)
    expect(groups[0].title).toBe('绪论 / 第 3 段')
    expect(groups[0].findings.map((item) => item.id)).toEqual(['font-1', 'paragraph-1'])
    expect(groups[1].title).toBe('第 10 段')
  })
})
