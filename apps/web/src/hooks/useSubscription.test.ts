import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

import { useSubscription } from './useSubscription'

const mockFetch = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useSubscription', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('starts in loading state', () => {
    mockFetch.mockReturnValue(new Promise(() => {})) // never resolves
    const { result } = renderHook(() => useSubscription())
    expect(result.current.loading).toBe(true)
    expect(result.current.subscription).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('returns subscription data on success', async () => {
    const data = {
      status: 'active',
      plan: 'monthly',
      current_period_end: 1735689600,
      stripe_customer_id: 'cus_abc',
      stripe_subscription_id: 'sub_abc',
    }
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ data }),
    })

    const { result } = renderHook(() => useSubscription())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.subscription).toEqual(data)
    expect(result.current.error).toBeNull()
  })

  it('returns null subscription when data is null', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ data: null }),
    })

    const { result } = renderHook(() => useSubscription())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.subscription).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('returns error on network failure', async () => {
    mockFetch.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useSubscription())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.subscription).toBeNull()
    expect(result.current.error).toBe('Network error')
  })

  it('returns error message from API 500 response', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({
        error: { code: 'SUBSCRIPTION_FETCH_FAILED', message: 'Unable to load subscription data' },
      }),
    })

    const { result } = renderHook(() => useSubscription())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.subscription).toBeNull()
    expect(result.current.error).toBe('Unable to load subscription data')
  })

  it('returns error on Zod validation failure', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ data: { status: 'invalid_status' } }),
    })

    const { result } = renderHook(() => useSubscription())

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.subscription).toBeNull()
    expect(result.current.error).toBe('Invalid subscription data')
  })
})
