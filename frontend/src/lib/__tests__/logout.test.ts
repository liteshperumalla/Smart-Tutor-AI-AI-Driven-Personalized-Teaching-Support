/**
 * logout(): finishes for a session the server already rejects, but surfaces
 * failures that may leave the HttpOnly cookies valid.
 */

import { logout } from '../api'

function respond(status: number) {
  ;(global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    statusText: 'status',
    json: async () => (status === 200 ? { success: true } : { detail: `failed ${status}` }),
  })
}

describe('logout', () => {
  beforeEach(() => {
    ;(global.fetch as jest.Mock).mockReset()
  })

  it('posts to /auth/logout with credentials', async () => {
    respond(200)
    await expect(logout()).resolves.toBeUndefined()
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0]
    expect(String(url)).toMatch(/\/auth\/logout$/)
    expect(init).toMatchObject({ method: 'POST', credentials: 'include' })
  })

  it.each([401, 403])('treats %i as already signed out', async (status) => {
    respond(status)
    await expect(logout()).resolves.toBeUndefined()
  })

  it.each([500, 502, 503])('rethrows %i so the client stays signed in', async (status) => {
    respond(status)
    await expect(logout()).rejects.toThrow(`failed ${status}`)
  })

  it('rethrows network failures', async () => {
    ;(global.fetch as jest.Mock).mockRejectedValueOnce(new TypeError('offline'))
    await expect(logout()).rejects.toThrow(/Network request failed/)
  })
})
