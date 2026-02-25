/**
 * Manual mock for @/lib/auth
 *
 * auth.ts has "use client" which causes next/jest's SWC transform to generate
 * RSC boundary stubs that can't be resolved in the jsdom test environment.
 * This stub exports the same symbols without any browser/client dependencies.
 */

export const AUTH_EXPIRED_EVENT = 'smart-ai-tutor-auth-expired'
export const AUTH_STATE_CHANGED_EVENT = 'smart-ai-tutor-auth-changed'

export const saveAuthToken = jest.fn()
export const getAuthToken = jest.fn().mockReturnValue(null)
export const clearAuthToken = jest.fn()
export const checkAuthStatus = jest.fn().mockResolvedValue(false)
