import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGetAnalytics = vi.fn()
const mockIsSupported = vi.fn()

vi.mock('@/lib/firebase/client', () => ({
  app: { name: '[DEFAULT]' },
}))

vi.mock('firebase/analytics', () => ({
  getAnalytics: mockGetAnalytics,
  isSupported: mockIsSupported,
}))

describe('loadAnalytics', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    mockIsSupported.mockResolvedValue(true)
  })

  it('initializes analytics when supported', async () => {
    const { loadAnalytics } = await import('./analytics')
    await loadAnalytics()
    expect(mockIsSupported).toHaveBeenCalled()
    expect(mockGetAnalytics).toHaveBeenCalled()
  })

  it('does not initialize analytics when not supported', async () => {
    mockIsSupported.mockResolvedValue(false)
    const { loadAnalytics } = await import('./analytics')
    await loadAnalytics()
    expect(mockGetAnalytics).not.toHaveBeenCalled()
  })

  it('only initializes once (singleton guard)', async () => {
    const { loadAnalytics } = await import('./analytics')
    await loadAnalytics()
    await loadAnalytics()
    expect(mockGetAnalytics).toHaveBeenCalledTimes(1)
  })

  it('silently catches errors when firebase is unavailable', async () => {
    mockIsSupported.mockRejectedValue(new Error('Firebase not available'))
    const { loadAnalytics } = await import('./analytics')
    await expect(loadAnalytics()).resolves.toBeUndefined()
  })
})
