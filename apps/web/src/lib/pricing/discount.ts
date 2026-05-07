import type { Plan } from '@/lib/pricing/plans'
import type { AppliedCoupon } from '@/components/checkout/CheckoutContext'

export type DiscountResult = {
  discountedCents: number
  deferredUntil: Date | null
}

function addMonthsUTC(date: Date, months: number): Date {
  const d = new Date(date)
  d.setUTCDate(1)
  d.setUTCMonth(d.getUTCMonth() + months)
  const lastDay = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate()
  d.setUTCDate(Math.min(date.getUTCDate(), lastDay))
  return d
}

export function computeDiscountedPrice(plan: Plan, coupon: AppliedCoupon): DiscountResult {
  let discountedCents: number

  if (coupon.percentOff !== null) {
    if (coupon.percentOff === 100) {
      discountedCents = 0
    } else {
      discountedCents = Math.round(plan.priceCents * (1 - coupon.percentOff / 100))
    }
  } else if (coupon.amountOffCents !== null) {
    discountedCents = Math.max(0, plan.priceCents - coupon.amountOffCents)
  } else {
    discountedCents = plan.priceCents
  }

  const deferredUntil =
    discountedCents === 0 && coupon.durationInMonths !== null
      ? addMonthsUTC(new Date(), coupon.durationInMonths)
      : null

  return { discountedCents, deferredUntil }
}
