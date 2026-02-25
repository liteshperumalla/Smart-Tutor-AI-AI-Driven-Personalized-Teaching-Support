/**
 * Manual mock for @/lib/api
 *
 * next/jest's SWC transform converts "@/lib/api" → "../../lib/api" (relative)
 * BEFORE Jest's moduleNameMapper fires. The real api.ts imports auth.ts which
 * has "use client", causing SWC to generate RSC boundary code that cannot be
 * resolved in the jsdom test environment. This stub avoids that entire chain.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export const API_BASE_URL: string = API_BASE

export function getApiBaseUrl(): string {
  return API_BASE
}

// Async stubs for functions imported by pages under test
export const fetchHealth = jest.fn().mockResolvedValue({ status: 'ok' })
export const fetchHomeOverview = jest.fn().mockResolvedValue({})
export const postJSON = jest.fn().mockResolvedValue({})
export const patchJSON = jest.fn().mockResolvedValue({})
export const deleteJSON = jest.fn().mockResolvedValue({})
export const getJSON = jest.fn().mockResolvedValue({})
