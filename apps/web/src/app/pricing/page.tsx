import type { Metadata } from 'next'

import { CheckoutProvider, type AppliedCoupon } from '@/components/checkout/CheckoutContext'
import { CouponInput } from '@/components/checkout/CouponInput'
import { PlanCard } from '@/components/checkout/PlanCard'
import { PLAN_MONTHLY, PLAN_YEARLY } from '@/lib/pricing/plans'
import { previewCoupon } from '@/lib/stripe/coupons'

export const metadata: Metadata = {
  title: 'Pricing — Warden',
  description:
    'Simple, honest pricing for Warden. Choose a monthly or yearly plan and get full access to session review, clip export, and minimap analysis.',
  openGraph: {
    title: 'Pricing — Warden',
    description:
      'Simple, honest pricing for Warden. Choose a monthly or yearly plan and get full access to session review, clip export, and minimap analysis.',
    type: 'website',
    locale: 'en_US',
    siteName: 'Warden',
  },
}

type PricingPageProps = {
  searchParams?: Promise<{ checkout?: string; coupon?: string }>
}

export default async function PricingPage({ searchParams }: PricingPageProps) {
  const resolved = (await searchParams) ?? {}
  const canceled = resolved.checkout === 'canceled'

  let initialCoupon: AppliedCoupon | undefined = undefined
  const couponParam = resolved.coupon?.trim()
  if (couponParam && couponParam.length > 0) {
    try {
      const result = await previewCoupon(couponParam)
      if (result) initialCoupon = result.coupon
    } catch (err) {
      console.warn('[pricing] coupon preview failed', err)
    }
  }

  return (
    <div className="flex flex-1 flex-col">
      <section className="mx-auto flex w-full max-w-5xl flex-col items-center gap-4 px-4 py-8 text-center md:px-8 md:py-12">
        <h1 className="text-foreground max-w-2xl text-[2rem] leading-[1.2] font-extrabold tracking-tight md:text-[3rem]">
          Simple, honest pricing
        </h1>
        <p className="text-muted-foreground max-w-xl text-base leading-relaxed md:text-lg">
          One plan, two billing options. Full access to every Warden feature — no tiers, no
          surprises.
        </p>
      </section>

      <section
        aria-labelledby="plans-heading"
        className="mx-auto w-full max-w-5xl px-4 py-8 md:px-8 md:py-12"
      >
        <h2 id="plans-heading" className="sr-only">
          Subscription plans
        </h2>
        {canceled && (
          <p
            data-testid="checkout-canceled-banner"
            className="text-muted-foreground border-border mb-6 rounded-[6px] border px-4 py-3 text-sm"
          >
            Checkout canceled — you can try again anytime.
          </p>
        )}
        <CheckoutProvider initialCoupon={initialCoupon}>
          <CouponInput />
          <div className="grid gap-6 md:grid-cols-2">
            <PlanCard plan={PLAN_MONTHLY} />
            <PlanCard plan={PLAN_YEARLY} />
          </div>
        </CheckoutProvider>
      </section>
    </div>
  )
}
