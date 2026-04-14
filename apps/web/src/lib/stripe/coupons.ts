import 'server-only'

import { getStripe } from '@/lib/stripe/server'

import type { AppliedCoupon } from '@/components/checkout/CheckoutContext'

export type PreviewCouponResult = {
  coupon: AppliedCoupon
  promotionCodeId: string
}

export async function previewCoupon(code: string): Promise<PreviewCouponResult | null> {
  const trimmed = code.trim()
  if (trimmed.length === 0) return null

  const stripe = getStripe()
  const list = await stripe.promotionCodes.list({
    code: trimmed,
    active: true,
    limit: 1,
    expand: ['data.promotion.coupon'],
  })

  const promo = list.data[0]
  if (!promo) return null
  if (promo.active === false) return null

  const expiresAt = promo.expires_at
  if (typeof expiresAt === 'number' && expiresAt * 1000 < Date.now()) return null

  const promotion = promo.promotion
  const couponField = promotion?.coupon
  const couponObject = couponField && typeof couponField === 'object' ? couponField : null
  if (!couponObject || couponObject.valid === false) return null

  const percentOff =
    typeof couponObject.percent_off === 'number' && couponObject.percent_off > 0
      ? couponObject.percent_off
      : null
  const amountOffCents =
    typeof couponObject.amount_off === 'number' && couponObject.amount_off > 0
      ? couponObject.amount_off
      : null

  if (percentOff === null && amountOffCents === null) return null

  const durationInMonths =
    couponObject.duration === 'repeating' && typeof couponObject.duration_in_months === 'number'
      ? couponObject.duration_in_months
      : null

  return {
    coupon: {
      code: trimmed,
      percentOff,
      amountOffCents,
      durationInMonths,
    },
    promotionCodeId: promo.id,
  }
}
