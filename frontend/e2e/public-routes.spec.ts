import { expect, test } from 'playwright/test'

test.describe('Public application routes', () => {
  test('renders the multi-course home page', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('heading', { name: 'Smart AI Tutor' })).toBeVisible()
    await expect(page.getByText('multi-course learning platform', { exact: false })).toBeVisible()
    await expect(page.locator('a[href="/chat"]').first()).toBeVisible()
  })

  test('renders the sign-in form and enabled Google option', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    await expect(page.locator('input[name="username"]')).toBeVisible()
    await expect(page.locator('input[name="password"]')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Sign in with Google' })).toBeEnabled()
  })

  test('does not render protected admin content for an anonymous visitor', async ({ page }) => {
    await page.goto('/admin')

    // The route proxy sends signed-out visitors to sign in, then back here.
    await expect(page).toHaveURL(/\/login\?next=%2Fadmin$/)
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    await expect(page.getByText('Admin Panel')).not.toBeVisible()
  })

  test('sends anonymous visitors on other app pages to sign in', async ({ page }) => {
    for (const path of ['/profile', '/feedback', '/resources', '/appointments']) {
      await page.goto(path)
      await expect(page).toHaveURL(new RegExp(`/login\\?next=${encodeURIComponent(path)}$`))
    }
  })
})
