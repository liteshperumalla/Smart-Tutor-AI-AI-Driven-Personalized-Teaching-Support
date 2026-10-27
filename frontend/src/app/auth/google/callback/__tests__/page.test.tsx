/**
 * The password-setup token from Google sign-in never travels in the URL.
 */

import { render, screen, waitFor } from '@testing-library/react'
import GoogleCallbackPage from '../page'

const replace = jest.fn()
const state = btoa(JSON.stringify({ intent: 'login', next: '/', nonce: 'n1' }))

jest.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams({ code: 'c', state }),
}))

describe('Google callback password-setup handoff', () => {
  afterEach(() => jest.restoreAllMocks())

  beforeEach(() => {
    replace.mockReset()
    sessionStorage.clear()
    jest.spyOn(document, 'cookie', 'get').mockReturnValue('google_oauth_nonce=n1')
    global.fetch = jest.fn().mockResolvedValue({
      status: 428,
      ok: false,
      json: async () => ({ requires_password_setup: true, password_setup_token: 'secret-token', username: 'ada' }),
    }) as jest.Mock
  })

  it('stashes the token and navigates without it', async () => {
    render(<GoogleCallbackPage />)
    await waitFor(() => expect(replace).toHaveBeenCalled())
    const url = replace.mock.calls[0][0] as string
    expect(url.startsWith('/password-setup?')).toBe(true)
    expect(url).not.toContain('secret-token')
    expect(url).not.toContain('ada')
  })

  it('shows an error instead of putting the token in the URL when storage fails', async () => {
    const spy = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    render(<GoogleCallbackPage />)
    expect(await screen.findByText(/blocked session storage/)).toBeInTheDocument()
    expect(replace).not.toHaveBeenCalled()
    spy.mockRestore()
  })
})
