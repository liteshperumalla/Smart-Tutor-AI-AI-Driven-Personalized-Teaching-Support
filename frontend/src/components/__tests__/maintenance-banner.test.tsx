/**
 * Maintenance banner tests: shown only when the backend is unreachable.
 */

import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { MaintenanceBanner } from '../maintenance-banner'

jest.mock('@/lib/maintenance', () => ({
  WINDOW_LABEL: 'Mon–Fri 9 AM–5 PM CT',
  getMaintenanceState: jest.fn(() => ({ isDown: true, resumesLabel: 'Monday at 9:00 AM CT' })),
}))

class ResizeObserverStub {
  observe() {}
  disconnect() {}
}

describe('MaintenanceBanner', () => {
  const originalFetch = global.fetch

  beforeAll(() => {
    ;(global as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub
  })

  afterEach(() => {
    global.fetch = originalFetch
    document.documentElement.style.removeProperty('--banner-h')
  })

  it('stays hidden when the backend answers, even inside the stop window', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true }) as unknown as typeof fetch

    render(<MaintenanceBanner />)

    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/backend/health', { cache: 'no-store' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows the scheduled-maintenance notice when the backend is unreachable', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false }) as unknown as typeof fetch

    render(<MaintenanceBanner />)

    expect(await screen.findByRole('status')).toHaveTextContent('Service resumes Monday at 9:00 AM CT.')
  })

  it('treats a network error as unreachable', async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError('Failed to fetch')) as unknown as typeof fetch

    render(<MaintenanceBanner />)

    expect(await screen.findByRole('status')).toHaveTextContent('Scheduled maintenance')
  })
})
