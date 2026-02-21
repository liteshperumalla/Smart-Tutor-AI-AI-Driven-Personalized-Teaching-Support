/**
 * E2E Tests for Chat Functionality
 */

import { test, expect } from '@playwright/test'

test.describe('Chat Functionality', () => {
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto('/login')
    await page.fill('input[name="username"]', 'testuser')
    await page.fill('input[name="password"]', 'TestPass123!')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')
  })

  test('should create new chat session', async ({ page }) => {
    await page.goto('/chat')
    await page.click('text=New chat')

    // Session should be created
    await expect(page.locator('text=New chat')).toBeVisible()
  })

  test('should send message in chat', async ({ page }) => {
    await page.goto('/chat')

    // Create session if not exists
    const sessionExists = await page.locator('text=New chat').isVisible()
    if (!sessionExists) {
      await page.click('text=New chat')
    }

    // Send message
    await page.fill('textarea[placeholder*="Ask anything"]', 'What is machine learning?')
    await page.click('button:has-text("Send")')

    // Message should appear
    await expect(page.locator('text=What is machine learning?')).toBeVisible()

    // Response should appear (wait for streaming)
    await expect(page.locator('[class*="assistant"]')).toBeVisible({ timeout: 30000 })
  })

  test('should list chat sessions', async ({ page }) => {
    await page.goto('/chat')

    // Sessions list should be visible
    await expect(page.locator('text=Recent chats')).toBeVisible()
  })

  test('should show streaming indicator while response is being generated', async ({ page }) => {
    await page.goto('/chat')

    // Create a fresh session
    await page.click('text=New chat')

    // Type a question
    await page.fill('textarea[placeholder*="Ask anything"]', 'What is machine learning in one sentence?')
    await page.click('button:has-text("Send")')

    // User message should appear immediately
    await expect(page.locator('text=What is machine learning in one sentence?')).toBeVisible()

    // A streaming / thinking indicator should appear during generation
    // The app may show a spinner, "Thinking…", or an animated placeholder
    const streamingIndicator = page.locator(
      '[data-testid="streaming-indicator"], [class*="streaming"], [class*="thinking"], [class*="animate-pulse"]'
    ).first()
    await expect(streamingIndicator).toBeVisible({ timeout: 10000 })

    // Eventually the streaming indicator should disappear once the response is done
    await expect(streamingIndicator).not.toBeVisible({ timeout: 60000 })
  })

  test('should not allow sending empty messages', async ({ page }) => {
    await page.goto('/chat')
    await page.click('text=New chat')

    // The send button should be disabled when textarea is empty
    const sendButton = page.locator('button:has-text("Send")')
    await expect(sendButton).toBeDisabled()
  })
})
