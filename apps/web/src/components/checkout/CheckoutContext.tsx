'use client'

import { createContext, useCallback, useContext, useMemo, useState } from 'react'

import type { ReactNode } from 'react'

export type AppliedCoupon = {
  code: string
  percentOff: number | null
  amountOffCents: number | null
  durationInMonths: number | null
}

export type CheckoutContextValue = {
  coupon: AppliedCoupon | null
  applyCoupon: (coupon: AppliedCoupon) => void
  clearCoupon: () => void
}

const CheckoutContext = createContext<CheckoutContextValue | undefined>(undefined)

export function CheckoutProvider({
  children,
  initialCoupon,
}: {
  children: ReactNode
  initialCoupon?: AppliedCoupon
}) {
  const [coupon, setCoupon] = useState<AppliedCoupon | null>(initialCoupon ?? null)

  const applyCoupon = useCallback((next: AppliedCoupon) => {
    setCoupon(next)
  }, [])

  const clearCoupon = useCallback(() => {
    setCoupon(null)
  }, [])

  const value = useMemo<CheckoutContextValue>(
    () => ({ coupon, applyCoupon, clearCoupon }),
    [coupon, applyCoupon, clearCoupon],
  )

  return <CheckoutContext.Provider value={value}>{children}</CheckoutContext.Provider>
}

export function useCheckout(): CheckoutContextValue {
  const ctx = useContext(CheckoutContext)
  if (ctx === undefined) {
    throw new Error('useCheckout must be used within a CheckoutProvider')
  }
  return ctx
}
