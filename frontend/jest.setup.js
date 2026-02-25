/**
 * Jest Setup File
 * Runs before all tests
 */

import '@testing-library/jest-dom'

// Mock @/lib/api globally — avoids jest.mock hoist resolution issues in CI
// (babel-plugin-jest-hoist bypasses moduleNameMapper; setup-file mocks do not)
jest.mock('@/lib/api', () => ({
  getApiBaseUrl: jest.fn(() => 'http://localhost:8000/api/v1'),
  API_BASE_URL: 'http://localhost:8000/api/v1',
}))

// Mock Google Auth Button globally — not relevant to form behavior tests
jest.mock('@/components/google-auth-button', () => ({
  GoogleAuthButton: () => null,
}))

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter() {
    return {
      push: jest.fn(),
      replace: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
    }
  },
  useSearchParams() {
    return {
      get: jest.fn(),
    }
  },
  usePathname() {
    return '/'
  },
}))

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
})

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}
global.localStorage = localStorageMock

// Mock fetch
global.fetch = jest.fn()

// Suppress console errors in tests
global.console = {
  ...console,
  error: jest.fn(),
  warn: jest.fn(),
}
