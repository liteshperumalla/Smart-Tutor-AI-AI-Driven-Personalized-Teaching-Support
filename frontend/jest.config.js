/**
 * Jest Configuration for Smart AI Tutor Frontend
 */

// Set env vars before any module loads so api.ts constants are initialised correctly.
// This avoids jest.mock('@/lib/api') which fails in CI when the module chain
// includes a "use client" file (auth.ts) that next/jest can't resolve for mocking.
process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost:8000/api/v1'

// eslint-disable-next-line @typescript-eslint/no-require-imports
const nextJest = require('next/jest')

const createJestConfig = nextJest({
  // Provide the path to your Next.js app to load next.config.js and .env files in your test environment
  dir: './',
})

// Add any custom config to be passed to Jest
const customJestConfig = {
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
  moduleNameMapper: {
    // Intercept @/lib/api in BOTH alias form ("@/lib/api") and the relative-path
    // form ("../../lib/api") that next/jest's SWC emits after resolving tsconfig paths.
    // Must come BEFORE the generic ^@/ catch-all so it takes precedence.
    '/lib/api$': '<rootDir>/src/lib/__mocks__/api.ts',
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  collectCoverageFrom: [
    'src/**/*.{js,jsx,ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/*.stories.{js,jsx,ts,tsx}',
    '!src/**/__tests__/**',
  ],
  coverageThreshold: {
    global: {
      branches: 0,
      functions: 0,
      lines: 0,
      statements: 0,
    },
  },
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.{js,jsx,ts,tsx}',
    '<rootDir>/src/**/*.{spec,test}.{js,jsx,ts,tsx}',
  ],
}

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config which is async
module.exports = createJestConfig(customJestConfig)
