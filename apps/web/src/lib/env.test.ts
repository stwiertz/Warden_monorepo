import { describe, it, expect, beforeAll } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

describe('.env.example client/server split (FR34 tripwire)', () => {
  let lines: string[] = []

  beforeAll(() => {
    const envExample = readFileSync(resolve(process.cwd(), '.env.example'), 'utf-8')
    lines = envExample.split(/\r?\n/)
  })

  it('does not expose STRIPE_SECRET_KEY as NEXT_PUBLIC_', () => {
    expect(lines.some((l) => /^NEXT_PUBLIC_STRIPE_SECRET_KEY\b/.test(l))).toBe(false)
  })

  it('does not expose STRIPE_WEBHOOK_SECRET as NEXT_PUBLIC_', () => {
    expect(lines.some((l) => /^NEXT_PUBLIC_STRIPE_WEBHOOK_SECRET\b/.test(l))).toBe(false)
  })

  it('does not expose FIREBASE_SERVICE_ACCOUNT_KEY as NEXT_PUBLIC_', () => {
    expect(lines.some((l) => /^NEXT_PUBLIC_FIREBASE_SERVICE_ACCOUNT_KEY\b/.test(l))).toBe(false)
  })

  it('declares STRIPE_SECRET_KEY server-only', () => {
    expect(lines.some((l) => /^STRIPE_SECRET_KEY\b/.test(l))).toBe(true)
  })

  it('declares STRIPE_WEBHOOK_SECRET server-only', () => {
    expect(lines.some((l) => /^STRIPE_WEBHOOK_SECRET\b/.test(l))).toBe(true)
  })

  it('declares FIREBASE_SERVICE_ACCOUNT_KEY server-only', () => {
    expect(lines.some((l) => /^FIREBASE_SERVICE_ACCOUNT_KEY\b/.test(l))).toBe(true)
  })

  it('declares STRIPE_PRICE_MONTHLY server-only (no NEXT_PUBLIC_ prefix)', () => {
    expect(lines.some((l) => /^STRIPE_PRICE_MONTHLY\b/.test(l))).toBe(true)
    expect(lines.some((l) => /^NEXT_PUBLIC_STRIPE_PRICE_MONTHLY\b/.test(l))).toBe(false)
  })

  it('declares STRIPE_PRICE_YEARLY server-only (no NEXT_PUBLIC_ prefix)', () => {
    expect(lines.some((l) => /^STRIPE_PRICE_YEARLY\b/.test(l))).toBe(true)
    expect(lines.some((l) => /^NEXT_PUBLIC_STRIPE_PRICE_YEARLY\b/.test(l))).toBe(false)
  })

  it('declares NEXT_PUBLIC_APP_URL as a client-safe public value', () => {
    expect(lines.some((l) => /^NEXT_PUBLIC_APP_URL\b/.test(l))).toBe(true)
  })
})
