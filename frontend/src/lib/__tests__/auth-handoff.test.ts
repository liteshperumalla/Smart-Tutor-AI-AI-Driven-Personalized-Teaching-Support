/**
 * Identity fields travel between auth pages through sessionStorage, not the URL.
 */

import { clearAuthHandoff, readAuthHandoff, stashAuthHandoff } from '../auth-handoff'

const noQuery = new URLSearchParams()

describe('auth handoff', () => {
  beforeEach(() => sessionStorage.clear())

  it('round-trips values for the target page only', () => {
    stashAuthHandoff('verify', { username: 'ada', email: 'ada@example.com' })
    expect(readAuthHandoff('verify', noQuery)).toEqual({
      username: 'ada',
      email: 'ada@example.com',
      token: undefined,
      fromUrl: false,
    })
    expect(readAuthHandoff('password-setup', noQuery).username).toBeUndefined()
  })

  it('still accepts legacy query-string links and flags them for removal', () => {
    const query = new URLSearchParams({ username: 'ada', token: 't0k' })
    expect(readAuthHandoff('password-reset', query)).toMatchObject({
      username: 'ada',
      token: 't0k',
      fromUrl: true,
    })
  })

  it('survives a refresh of the receiving page', () => {
    stashAuthHandoff('verify', { username: 'ada' })
    readAuthHandoff('verify', noQuery)
    expect(readAuthHandoff('verify', noQuery).username).toBe('ada')
  })
})

describe('auth handoff completion and failures', () => {
  beforeEach(() => sessionStorage.clear())

  it('clears a completed handoff so a later visit does not prefill it', () => {
    stashAuthHandoff('verify', { username: 'ada' })
    clearAuthHandoff('verify')
    expect(readAuthHandoff('verify', new URLSearchParams()).username).toBeUndefined()
  })

  it('reports when storage rejects the write', () => {
    const spy = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    expect(stashAuthHandoff('password-setup', { token: 't' })).toBe(false)
    spy.mockRestore()
    expect(stashAuthHandoff('password-setup', { token: 't' })).toBe(true)
  })
})
