import 'server-only'

import Stripe from 'stripe'

import type { Plan } from '@/lib/pricing/plans'

const STRIPE_API_VERSION = '2026-04-22.dahlia'

let _stripe: Stripe | null = null

export function getStripe(): Stripe {
  if (_stripe) return _stripe
  const key = process.env.STRIPE_SECRET_KEY
  if (!key) {
    throw new Error('STRIPE_SECRET_KEY is not set in the environment')
  }
  _stripe = new Stripe(key, { apiVersion: STRIPE_API_VERSION })
  return _stripe
}

export function getPlanPriceId(plan: Plan): string | null {
  const value = process.env[plan.stripePriceEnvKey]
  return value && value.length > 0 ? value : null
}

const RETRY_DELAYS_MS = [250, 750, 2250] as const

function isTransientStripeError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false
  const e = err as { type?: unknown; statusCode?: unknown }
  const status = typeof e.statusCode === 'number' ? e.statusCode : undefined
  if (e.type === 'StripeConnectionError') return true
  if (e.type === 'StripeRateLimitError') return true
  // Per AC #4: StripeAPIError is only transient on 5xx. Absent statusCode treated as transient
  // because the Stripe SDK uses StripeAPIError as a 5xx-class base by default.
  if (e.type === 'StripeAPIError' && (status === undefined || (status >= 500 && status < 600))) {
    return true
  }
  if (status !== undefined && status >= 500 && status < 600) return true
  return false
}

export async function retryStripeCall<T>(fn: () => Promise<T>, label: string): Promise<T> {
  let lastErr: unknown
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await fn()
    } catch (err) {
      lastErr = err
      if (!isTransientStripeError(err)) {
        console.error(
          `[stripe/retry ${new Date().toISOString()}] ${label} non-transient error, not retrying:`,
          err,
        )
        throw err
      }
      if (attempt < 2) {
        console.error(
          `[stripe/retry ${new Date().toISOString()}] ${label} retry ${attempt + 1}/3 failed:`,
          err,
        )
        await new Promise((r) => setTimeout(r, RETRY_DELAYS_MS[attempt]))
      }
    }
  }
  console.error(`[stripe/retry ${new Date().toISOString()}] ${label} exhausted retries`)
  throw lastErr
}
