/**
 * Identity fields travel between auth pages through sessionStorage, not the URL.
 */

import { readAuthHandoff, stashAuthHandoff } from '../auth-handoff'

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
