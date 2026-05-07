import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

import { computeDiscountedPrice } from './discount'
import { PLAN_MONTHLY, PLAN_YEARLY } from './plans'

import type { AppliedCoupon } from '@/components/checkout/CheckoutContext'

function coupon(overrides: Partial<AppliedCoupon> = {}): AppliedCoupon {
  return {
    code: 'TEST',
    percentOff: null,
    amountOffCents: null,
    durationInMonths: null,
    ...overrides,
  }
}

describe('computeDiscountedPrice', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(Date.UTC(2026, 0, 15, 12, 0, 0)))
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('100% repeating coupon zeroes the price and computes a deferred date', () => {
    const result = computeDiscountedPrice(
      PLAN_MONTHLY,
      coupon({ percentOff: 100, durationInMonths: 3 }),
    )
    expect(result.discountedCents).toBe(0)
    expect(result.deferredUntil).not.toBeNull()
    expect(result.deferredUntil!.toISOString()).toBe('2026-04-15T12:00:00.000Z')
  })

  it('50% percent-off halves the price with no deferred date', () => {
    const result = computeDiscountedPrice(PLAN_MONTHLY, coupon({ percentOff: 50 }))
    expect(result.discountedCents).toBe(400)
    expect(result.deferredUntil).toBeNull()
  })

  it('500c amount-off subtracts cents with no deferred date', () => {
    const result = computeDiscountedPrice(PLAN_MONTHLY, coupon({ amountOffCents: 500 }))
    expect(result.discountedCents).toBe(299)
    expect(result.deferredUntil).toBeNull()
  })

  it('799c amount-off on monthly clamps to zero with no deferred date (no repeating)', () => {
    const result = computeDiscountedPrice(PLAN_MONTHLY, coupon({ amountOffCents: 799 }))
    expect(result.discountedCents).toBe(0)
    expect(result.deferredUntil).toBeNull()
  })

  it('100% repeating coupon clamps Jan 31 + 1 month to Feb 28', () => {
    vi.setSystemTime(new Date(Date.UTC(2026, 0, 31, 0, 0, 0)))
    const result = computeDiscountedPrice(
      PLAN_YEARLY,
      coupon({ percentOff: 100, durationInMonths: 1 }),
    )
    expect(result.discountedCents).toBe(0)
    expect(result.deferredUntil).not.toBeNull()
    expect(result.deferredUntil!.toISOString().slice(0, 10)).toBe('2026-02-28')
  })

  it('100% forever coupon (no durationInMonths) returns null deferredUntil', () => {
    const result = computeDiscountedPrice(
      PLAN_MONTHLY,
      coupon({ percentOff: 100, durationInMonths: null }),
    )
    expect(result.discountedCents).toBe(0)
    expect(result.deferredUntil).toBeNull()
  })
})
