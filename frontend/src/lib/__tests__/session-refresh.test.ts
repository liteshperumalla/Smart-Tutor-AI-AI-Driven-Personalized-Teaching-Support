/**
 * A lapsed 15-minute access token is renewed from the 7-day refresh token
 * instead of signing the user out with "session expired".
 */

import { checkAuthStatus, refreshSession } from '../auth'
import { fetchCourses } from '../api'

type Reply = { status: number; body?: unknown }

function reply({ status, body = {} }: Reply) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'status',
    json: async () => body,
  }
}

function queue(...replies: Reply[]) {
  for (const r of replies) {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce(reply(r))
  }
}

function calledUrls(): string[] {
  return (global.fetch as jest.Mock).mock.calls.map(([url]) => String(url))
}

describe('session refresh', () => {
  beforeEach(() => {
    ;(global.fetch as jest.Mock).mockReset()
  })

  it('checkAuthStatus refreshes once on 401 and retries /auth/me', async () => {
    queue({ status: 401 }, { status: 200 }, { status: 200, body: { user: { username: 'u' } } })
    await expect(checkAuthStatus('/api/backend')).resolves.toBe(true)
    expect(calledUrls()).toEqual(['/api/backend/auth/me', '/api/backend/auth/refresh', '/api/backend/auth/me'])
  })

  it('checkAuthStatus reports signed out when the refresh is rejected', async () => {
    queue({ status: 401 }, { status: 401 })
    await expect(checkAuthStatus('/api/backend')).resolves.toBe(false)
    expect(calledUrls()).toHaveLength(2)
  })

  it('concurrent callers share one refresh (refresh tokens are single-use)', async () => {
    queue({ status: 200 })
    const results = await Promise.all([refreshSession('/b'), refreshSession('/b'), refreshSession('/b')])
    expect(results).toEqual([true, true, true])
    expect(global.fetch).toHaveBeenCalledTimes(1)
  })

  it('API calls retry after a successful refresh instead of expiring the session', async () => {
    const expired = jest.fn()
    window.addEventListener('smart-ai-tutor-auth-expired', expired)
    queue({ status: 401 }, { status: 200 }, { status: 200, body: { courses: [] } })

    await expect(fetchCourses('authenticated')).resolves.toEqual([])
    expect(calledUrls()[1]).toMatch(/\/auth\/refresh$/)
    expect(expired).not.toHaveBeenCalled()
    window.removeEventListener('smart-ai-tutor-auth-expired', expired)
  })

  it('API calls still expire the session when the refresh fails', async () => {
    const expired = jest.fn()
    window.addEventListener('smart-ai-tutor-auth-expired', expired)
    queue({ status: 401, body: { detail: 'Invalid or expired session' } }, { status: 401 })

    await expect(fetchCourses('authenticated')).rejects.toThrow('Invalid or expired session')
    expect(global.fetch).toHaveBeenCalledTimes(2)
    expect(expired).toHaveBeenCalled()
    window.removeEventListener('smart-ai-tutor-auth-expired', expired)
  })
})
