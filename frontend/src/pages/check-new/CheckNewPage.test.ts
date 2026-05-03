import { describe, expect, it } from 'vitest'

import { isSupportedWordFilename } from './CheckNewPage'

describe('isSupportedWordFilename', () => {
  it('accepts doc and docx filenames case-insensitively', () => {
    expect(isSupportedWordFilename('paper.doc')).toBe(true)
    expect(isSupportedWordFilename('paper.docx')).toBe(true)
    expect(isSupportedWordFilename('PAPER.DOC')).toBe(true)
    expect(isSupportedWordFilename('PAPER.DOCX')).toBe(true)
  })

  it('rejects unsupported extensions', () => {
    expect(isSupportedWordFilename('paper.pdf')).toBe(false)
    expect(isSupportedWordFilename('paper.docx.zip')).toBe(false)
    expect(isSupportedWordFilename('paper')).toBe(false)
  })
})
