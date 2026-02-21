/**
 * Login Page Tests
 * Tests form rendering, validation, error states, and submission behavior.
 */

import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import LoginPage from '../../app/login/page'

// next/link renders as a plain anchor in tests
jest.mock('next/link', () => {
  return function MockLink({ href, children }: { href: string; children: React.ReactNode }) {
    return <a href={href}>{children}</a>
  }
})

// Google OAuth button is not relevant to form behavior tests
jest.mock('@/components/google-auth-button', () => ({
  GoogleAuthButton: () => <button type="button">Continue with Google</button>,
}))

// Pin the API base URL so fetch calls are predictable
jest.mock('@/lib/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000/api/v1',
}))

const mockPush = jest.fn()

beforeEach(() => {
  jest.clearAllMocks()
  mockPush.mockClear()

  // Re-apply router mock with a stable push spy for each test
  jest.spyOn(require('next/navigation'), 'useRouter').mockReturnValue({
    push: mockPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
  })

  // Default: useSearchParams returns null for all keys (no ?signup= param)
  jest.spyOn(require('next/navigation'), 'useSearchParams').mockReturnValue({
    get: jest.fn().mockReturnValue(null),
  })

  // Default fetch: successful login
  ;(global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: async () => ({
      user: { username: 'testuser', email: 'test@test.com', full_name: 'Test User' },
      token_type: 'bearer',
      message: 'Tokens set in secure cookies.',
    }),
  })
})

describe('LoginPage', () => {
  it('renders username and password input fields', () => {
    render(<LoginPage />)

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('renders a Sign in submit button', () => {
    render(<LoginPage />)

    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('renders a link to the signup page', () => {
    render(<LoginPage />)

    const signupLink = screen.getByRole('link', { name: /create one/i })
    expect(signupLink).toHaveAttribute('href', '/signup')
  })

  it('calls the login API with entered credentials on submit', async () => {
    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'TestPass123' } })
    fireEvent.submit(document.querySelector('form')!)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/auth/login',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ username: 'testuser', password: 'TestPass123' }),
        })
      )
    })
  })

  it('redirects to home page after successful login', async () => {
    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'TestPass123' } })
    fireEvent.submit(document.querySelector('form')!)

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/')
    })
  })

  it('displays an error message when login fails', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Invalid username or password' }),
    })

    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'wrong' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } })
    fireEvent.submit(document.querySelector('form')!)

    await waitFor(() => {
      expect(screen.getByText(/Invalid username or password/i)).toBeInTheDocument()
    })
  })

  it('shows email verification prompt when backend reports unverified email', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Email not verified' }),
    })

    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'unverified' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'somepass' } })
    fireEvent.submit(document.querySelector('form')!)

    await waitFor(() => {
      // The unverified banner shows a "Resend code" button (unique to this state)
      expect(screen.getByRole('button', { name: /resend code/i })).toBeInTheDocument()
    })
  })

  it('shows signup success banner when ?signup=success is in URL', () => {
    jest.spyOn(require('next/navigation'), 'useSearchParams').mockReturnValue({
      get: jest.fn((key: string) => (key === 'signup' ? 'success' : null)),
    })

    render(<LoginPage />)

    expect(screen.getByText(/Account created successfully/i)).toBeInTheDocument()
  })

  it('disables the submit button while the request is in flight', async () => {
    // Never resolves during this test — simulates slow network
    ;(global.fetch as jest.Mock).mockImplementationOnce(() => new Promise(() => {}))

    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'user' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pass' } })

    await act(async () => {
      fireEvent.submit(document.querySelector('form')!)
    })

    expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()
  })
})
