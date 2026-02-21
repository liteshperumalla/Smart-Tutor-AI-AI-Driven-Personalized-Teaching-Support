/**
 * E2E Tests for Admin Access Control
 *
 * These tests verify that admin routes are protected from:
 *   1. Unauthenticated users (must redirect to login)
 *   2. Regular (non-admin) users (must be denied access)
 */

import { test, expect } from '@playwright/test'

/** Pages that should only be accessible to admins */
const ADMIN_PATHS = ['/admin', '/admin/users', '/admin/evaluation']

test.describe('Admin Access Control', () => {
  test('should redirect unauthenticated user from /admin to login', async ({ page }) => {
    await page.goto('/admin')

    // Must end up on the login page — never inside admin
    await expect(page).toHaveURL(/.*login/)
  })

  for (const adminPath of ADMIN_PATHS) {
    test(`should deny unauthenticated access to ${adminPath}`, async ({ page }) => {
      await page.goto(adminPath)

      // Should redirect away from admin
      await expect(page).not.toHaveURL(new RegExp(adminPath))
    })
  }

  test('should deny regular user access to admin dashboard', async ({ page }) => {
    // Log in as a non-admin user
    await page.goto('/login')
    await page.fill('input[name="username"]', 'testuser')
    await page.fill('input[name="password"]', 'TestPass123!')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')

    // Attempt to navigate to admin
    await page.goto('/admin')

    // Should be denied — either redirected away or shown an error
    const currentUrl = page.url()
    const isInsideAdmin = currentUrl.includes('/admin')
    if (isInsideAdmin) {
      // If we're still on an admin-prefixed URL the page must show an access-denied message
      const deniedIndicators = [
        page.locator('text=403'),
        page.locator('text=Forbidden'),
        page.locator('text=Unauthorized'),
        page.locator('text=Access denied'),
      ]
      const anyVisible = await Promise.any(
        deniedIndicators.map(loc => loc.isVisible())
      ).catch(() => false)
      expect(anyVisible).toBeTruthy()
    } else {
      // Redirected away from admin — that's also correct
      expect(currentUrl).not.toContain('/admin')
    }
  })

  test('should not expose admin navigation links to regular users', async ({ page }) => {
    // Log in as a non-admin user
    await page.goto('/login')
    await page.fill('input[name="username"]', 'testuser')
    await page.fill('input[name="password"]', 'TestPass123!')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')

    // Admin nav link must not be visible in the page chrome
    const adminNavLink = page.locator('a[href^="/admin"], a:has-text("Admin panel"), a:has-text("Admin Dashboard")')
    await expect(adminNavLink).not.toBeVisible()
  })

  test('admin evaluation page is gated', async ({ page }) => {
    // Navigate directly without auth
    await page.goto('/admin/evaluation')

    // Should not load the evaluation content — should go to login
    await expect(page).toHaveURL(/.*login/)
  })
})
