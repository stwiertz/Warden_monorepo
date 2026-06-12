// Story 1.10 (AR-1 / Decision #1) — strict-mode + no-`isPaid` regression guard
// for the generated `users/{uid}` wire contract.
//
// This test consumes the regenerated Zod surface from `@warden/contracts/user-doc`
// (output of `pnpm --filter @warden/contracts build`), proving the master JSON
// Schema's `additionalProperties: false` round-tripped to `.strict()` and that the
// legacy `isPaid` field is gone from the wire contract. It is a pure schema-parse
// test — no React/jsdom needed.
import { describe, it, expect } from 'vitest'
import { UserDocSchema } from '@warden/contracts/user-doc'

describe('UserDocSchema (generated wire contract) — strict mode', () => {
  it('accepts a minimal valid document ({ status, plan })', () => {
    const result = UserDocSchema.safeParse({ status: 'active', plan: 'monthly' })
    expect(result.success).toBe(true)
  })

  it('rejects an unknown key (additionalProperties:false → .strict())', () => {
    const result = UserDocSchema.safeParse({
      status: 'active',
      plan: 'monthly',
      bogus: true,
    })
    expect(result.success).toBe(false)
  })

  it('rejects the legacy `isPaid` field (dropped from the wire contract)', () => {
    const result = UserDocSchema.safeParse({
      status: 'active',
      plan: 'monthly',
      isPaid: false,
    })
    expect(result.success).toBe(false)
  })

  it('accepts optional `created_at` / `updated_at` string timestamps', () => {
    const result = UserDocSchema.safeParse({
      status: 'active',
      plan: 'monthly',
      created_at: '2026-06-12T00:00:00.000Z',
      updated_at: '2026-06-12T00:00:00.000Z',
    })
    expect(result.success).toBe(true)
  })

  it('accepts a full valid document with all optional billing fields', () => {
    const result = UserDocSchema.safeParse({
      status: 'past_due',
      plan: 'yearly',
      current_period_end: 1893456000,
      stripe_customer_id: 'cus_123',
      stripe_subscription_id: 'sub_123',
      created_at: '2026-06-12T00:00:00.000Z',
      updated_at: '2026-06-12T00:00:00.000Z',
    })
    expect(result.success).toBe(true)
  })
})
