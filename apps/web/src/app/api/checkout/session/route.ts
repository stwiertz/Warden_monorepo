import { z } from 'zod/v4'

import { adminAuth } from '@/lib/firebase/admin'
import { PLAN_BY_ID, PLAN_IDS } from '@/lib/pricing/plans'
import { previewCoupon } from '@/lib/stripe/coupons'
import { getPlanPriceId, getStripe } from '@/lib/stripe/server'

export const runtime = 'nodejs'

const SESSION_COOKIE_NAME = 'session'

const bodySchema = z.object({
  planId: z.enum(PLAN_IDS),
  couponCode: z.string().trim().min(1).max(64).optional(),
})

function envelopeError(code: string, message: string, status: number) {
  return Response.json({ error: { code, message } }, { status })
}

function readSessionCookie(request: Request): string | null {
  const header = request.headers.get('cookie')
  if (!header) return null
  for (const pair of header.split(/;\s*/)) {
    const eq = pair.indexOf('=')
    if (eq === -1) continue
    const name = pair.slice(0, eq)
    if (name === SESSION_COOKIE_NAME) {
      return decodeURIComponent(pair.slice(eq + 1))
    }
  }
  return null
}

function resolveAppUrl(request: Request): string {
  const fromEnv = process.env.NEXT_PUBLIC_APP_URL
  if (fromEnv && fromEnv.length > 0) return fromEnv.replace(/\/$/, '')
  return new URL(request.url).origin
}

export async function POST(request: Request) {
  let body: unknown
  try {
    body = await request.json()
  } catch {
    return envelopeError('INVALID_REQUEST', 'Request body must be valid JSON', 400)
  }

  const parsed = bodySchema.safeParse(body)
  if (!parsed.success) {
    return envelopeError('INVALID_REQUEST', 'planId must be "monthly" or "yearly"', 400)
  }

  const sessionCookie = readSessionCookie(request)
  if (!sessionCookie) {
    return envelopeError('UNAUTHENTICATED', 'Sign in required', 401)
  }

  let decoded: { uid: string; email?: string }
  try {
    const raw = (await adminAuth.verifySessionCookie(sessionCookie, true)) as {
      uid?: unknown
      email?: unknown
    }
    if (typeof raw.uid !== 'string' || raw.uid.length === 0) {
      return envelopeError('UNAUTHENTICATED', 'Sign in required', 401)
    }
    decoded = {
      uid: raw.uid,
      email: typeof raw.email === 'string' ? raw.email : undefined,
    }
  } catch {
    return envelopeError('UNAUTHENTICATED', 'Sign in required', 401)
  }

  const plan = PLAN_BY_ID[parsed.data.planId]
  const priceId = getPlanPriceId(plan)
  if (!priceId) {
    return envelopeError('MISSING_STRIPE_PRICE_ID', 'Stripe price is not configured', 500)
  }

  const appUrl = resolveAppUrl(request)

  let promotionCodeId: string | null = null
  if (parsed.data.couponCode) {
    try {
      const result = await previewCoupon(parsed.data.couponCode)
      if (!result) {
        return envelopeError('COUPON_INVALID', 'This coupon is no longer valid', 400)
      }
      promotionCodeId = result.promotionCodeId
    } catch {
      return envelopeError('CHECKOUT_FAILED', 'Unable to create checkout session', 500)
    }
  }

  try {
    const stripe = getStripe()
    const sessionArgs: Record<string, unknown> = {
      mode: 'subscription',
      line_items: [{ price: priceId, quantity: 1 }],
      success_url: `${appUrl}/dashboard?checkout=success&session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${appUrl}/pricing?checkout=canceled`,
      client_reference_id: decoded.uid,
      ...(decoded.email ? { customer_email: decoded.email } : {}),
      metadata: {
        firebase_uid: decoded.uid,
        plan_id: plan.id,
      },
      subscription_data: {
        metadata: {
          firebase_uid: decoded.uid,
          plan_id: plan.id,
        },
      },
    }
    if (promotionCodeId) {
      sessionArgs.discounts = [{ promotion_code: promotionCodeId }]
    } else {
      sessionArgs.allow_promotion_codes = true
    }
    const session = await stripe.checkout.sessions.create(
      sessionArgs as Parameters<typeof stripe.checkout.sessions.create>[0],
    )

    if (!session.url) {
      return envelopeError('CHECKOUT_FAILED', 'Stripe did not return a checkout URL', 500)
    }

    return Response.json({ data: { url: session.url } })
  } catch (err) {
    console.error('[checkout/session] stripe error:', err)
    return envelopeError('CHECKOUT_FAILED', 'Unable to create checkout session', 500)
  }
}
