/**
 * E2E Tests for Authentication Flow
 */

import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should register new user', async ({ page }) => {
    await page.click('text=Create one')
    await expect(page).toHaveURL(/.*signup/)

    const timestamp = Date.now()
    await page.fill('input[name="username"]', `testuser${timestamp}`)
    await page.fill('input[name="email"]', `test${timestamp}@example.com`)
    await page.fill('input[name="password"]', 'TestPass123!')
    await page.fill('input[name="confirmPassword"]', 'TestPass123!')

    await page.click('button[type="submit"]')

    // Should redirect to verify page
    await expect(page).toHaveURL(/.*verify/)
    await expect(page.locator('text=Verification')).toBeVisible()
  })

  test('should login with valid credentials', async ({ page }) => {
    await page.goto('/login')

    await page.fill('input[name="username"]', 'testuser')
    await page.fill('input[name="password"]', 'TestPass123!')
    await page.click('button[type="submit"]')

    // Should redirect to home page after login
    await expect(page).toHaveURL('/')
    await expect(page.locator('text=Profile')).toBeVisible()
  })

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('/login')

    await page.fill('input[name="username"]', 'invaliduser')
    await page.fill('input[name="password"]', 'wrongpassword')
    await page.click('button[type="submit"]')

    await expect(page.locator('text=Unable to sign in')).toBeVisible()
  })

  test('should logout user', async ({ page, context }) => {
    // Login first
    await page.goto('/login')
    await page.fill('input[name="username"]', 'testuser')
    await page.fill('input[name="password"]', 'TestPass123!')
    await page.click('button[type="submit"]')

    // Wait for redirect
    await page.waitForURL('/')

    // Click profile/logout
    await page.click('text=Profile')
    await page.click('text=Sign out')

    // Should redirect to login
    await expect(page).toHaveURL(/.*login/)

    // Token should be cleared
    const cookies = await context.cookies()
    const authCookie = cookies.find(c => c.name === 'access_token')
    expect(authCookie).toBeUndefined()
  })

  test('should redirect unauthenticated user from protected route to login', async ({ page }) => {
    // Navigate directly to a protected route without logging in
    await page.goto('/chat')

    // Should be redirected to login page
    await expect(page).toHaveURL(/.*login/)
  })

  test('should redirect to profile page without auth', async ({ page }) => {
    await page.goto('/profile')

    // Protected page — should land on login
    await expect(page).toHaveURL(/.*login/)
  })

  test('should preserve login page after logout', async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.fill('input[name="username"]', 'testuser')
    await page.fill('input[name="password"]', 'TestPass123!')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')

    // Logout via Profile menu
    await page.click('text=Profile')
    await page.click('text=Sign out')

    // Must end on login page — not be served a cached protected page
    await expect(page).toHaveURL(/.*login/)
    await expect(page.locator('input[name="username"]')).toBeVisible()
  })
})
