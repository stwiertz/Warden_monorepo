import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('server-only', () => ({}))

const mocks = vi.hoisted(() => {
  const mockTxGet = vi.fn()
  const mockTxCreate = vi.fn()
  const mockTxUpdate = vi.fn()
  const mockTxSet = vi.fn()
  const mockRunTransaction = vi.fn()
  const mockDocRef = { __ref: true } as unknown
  const mockDoc = vi.fn(() => mockDocRef)
  const mockCollection = vi.fn(() => ({ doc: mockDoc }))
  return {
    mockTxGet,
    mockTxCreate,
    mockTxUpdate,
    mockTxSet,
    mockRunTransaction,
    mockDocRef,
    mockDoc,
    mockCollection,
  }
})

vi.mock('firebase-admin/firestore', () => ({
  FieldValue: {
    serverTimestamp: () => '__SERVER_TIMESTAMP__',
  },
  Timestamp: class {
    constructor(public readonly millis: number) {}
    static fromMillis(ms: number) {
      return new this(ms)
    }
  },
}))

vi.mock('@/lib/firebase/admin', () => ({
  adminDb: {
    collection: (...args: unknown[]) => mocks.mockCollection(...args),
    runTransaction: (...args: unknown[]) => mocks.mockRunTransaction(...args),
  },
}))

// NOTE: No vi.mock('@/lib/stripe/server') here. This handler does not call
// getStripe / retryStripeCall; importing the real module would also crash on
// missing STRIPE_SECRET_KEY — a second tripwire against a future retrieve call
// sneaking in (AC #8 structural proof).

// NOTE: No vi.mock('stripe'). Same reasoning.

import { handleSubscriptionDeleted } from '@/lib/stripe/webhooks'
import type Stripe from 'stripe'

type SubShape = {
  id: string
  customer: string | { id: string }
  metadata?: Record<string, string>
}

function makeSub(overrides: Partial<SubShape> = {}): SubShape {
  return {
    id: 'sub_test_123',
    customer: 'cus_test_123',
    metadata: { firebase_uid: 'uid_abc', plan_id: 'monthly' },
    ...overrides,
  }
}

function makeDeletedEvent(overrides: Partial<SubShape> = {}, id = 'evt_sd_1'): Stripe.Event {
  return {
    id,
    type: 'customer.subscription.deleted',
    data: { object: makeSub(overrides) },
  } as unknown as Stripe.Event
}

function installRunTxWithSnap(
  exists: boolean,
  data: Record<string, unknown> = { status: 'active', plan: 'monthly' },
) {
  mocks.mockRunTransaction.mockImplementation(async (cb: (tx: unknown) => unknown) => {
    const tx = {
      get: (...args: unknown[]) => {
        mocks.mockTxGet(...args)
        return Promise.resolve({ exists, data: () => data })
      },
      create: (...args: unknown[]) => mocks.mockTxCreate(...args),
      update: (...args: unknown[]) => mocks.mockTxUpdate(...args),
      set: (...args: unknown[]) => mocks.mockTxSet(...args),
    }
    return cb(tx)
  })
}

describe('handleSubscriptionDeleted', () => {
  let errSpy: ReturnType<typeof vi.spyOn>
  let logSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.clearAllMocks()
    installRunTxWithSnap(true, { status: 'active', plan: 'monthly' })
    errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    logSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
  })

  afterEach(() => {
    errSpy.mockRestore()
    logSpy.mockRestore()
    vi.unstubAllEnvs()
  })

  it('happy path — active user flipped to canceled, minimal field bag', async () => {
    await handleSubscriptionDeleted(makeDeletedEvent())
    expect(mocks.mockCollection).toHaveBeenCalledWith('users')
    expect(mocks.mockDoc).toHaveBeenCalledWith('uid_abc')
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1)
    const [ref, fields] = mocks.mockTxUpdate.mock.calls[0]
    expect(ref).toBe(mocks.mockDocRef)
    expect(Object.keys(fields).sort()).toEqual(['status', 'updated_at'])
    expect(fields.status).toBe('canceled')
    expect(fields.updated_at).toBe('__SERVER_TIMESTAMP__')
    expect(mocks.mockTxCreate).not.toHaveBeenCalled()
    expect(mocks.mockTxSet).not.toHaveBeenCalled()
    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining('customer.subscription.deleted processed:'),
      'evt_sd_1',
      'uid_abc',
    )
  })

  it('happy path — past_due user flipped to canceled', async () => {
    installRunTxWithSnap(true, { status: 'past_due', plan: 'monthly' })
    await handleSubscriptionDeleted(makeDeletedEvent())
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1)
    const [, fields] = mocks.mockTxUpdate.mock.calls[0]
    expect(fields.status).toBe('canceled')
  })

  it('idempotent no-op — already canceled', async () => {
    installRunTxWithSnap(true, { status: 'canceled', plan: 'monthly' })
    await handleSubscriptionDeleted(makeDeletedEvent())
    expect(mocks.mockTxUpdate).not.toHaveBeenCalled()
    expect(mocks.mockTxCreate).not.toHaveBeenCalled()
    expect(mocks.mockTxSet).not.toHaveBeenCalled()
    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining('customer.subscription.deleted already canceled — no-op:'),
      'evt_sd_1',
      'uid_abc',
    )
    // no-op MUST NOT also emit a `processed:` line
    const processedCalls = logSpy.mock.calls.filter((c) => String(c[0]).includes('processed:'))
    expect(processedCalls).toHaveLength(0)
  })

  it('user doc missing — throws, no write', async () => {
    installRunTxWithSnap(false)
    await expect(handleSubscriptionDeleted(makeDeletedEvent())).rejects.toThrow(
      /user document not found/,
    )
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('user document not found — cannot update subscription state:'),
      'evt_sd_1',
      'uid_abc',
    )
    expect(mocks.mockTxUpdate).not.toHaveBeenCalled()
  })

  it('missing firebase_uid metadata — throws, runTransaction NOT called', async () => {
    await expect(handleSubscriptionDeleted(makeDeletedEvent({ metadata: {} }))).rejects.toThrow(
      /firebase_uid/,
    )
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('missing firebase_uid metadata — cannot link to user:'),
      'evt_sd_1',
      'sub_test_123',
    )
    expect(mocks.mockRunTransaction).not.toHaveBeenCalled()
  })

  it('Zod schema failure — missing id — throws, runTransaction NOT called', async () => {
    const badEvent = {
      id: 'evt_bad',
      type: 'customer.subscription.deleted',
      data: { object: { customer: 'cus_1', metadata: { firebase_uid: 'uid_x' } } },
    } as unknown as Stripe.Event
    await expect(handleSubscriptionDeleted(badEvent)).rejects.toThrow(/schema validation/)
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('payload failed schema validation:'),
      expect.anything(),
      'evt_bad',
    )
    expect(mocks.mockRunTransaction).not.toHaveBeenCalled()
  })

  it('customer as expanded object — schema accepts union second branch', async () => {
    await handleSubscriptionDeleted(makeDeletedEvent({ customer: { id: 'cus_obj' } }))
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1)
    const [, fields] = mocks.mockTxUpdate.mock.calls[0]
    expect(fields.status).toBe('canceled')
  })

  it('Firestore transaction throws — handler propagates', async () => {
    mocks.mockRunTransaction.mockRejectedValueOnce(new Error('permission-denied'))
    await expect(handleSubscriptionDeleted(makeDeletedEvent())).rejects.toThrow('permission-denied')
  })

  it('idempotent replay: second invocation (already canceled) is a no-op (AC #5 end-to-end)', async () => {
    // First invocation: active → canceled (write).
    installRunTxWithSnap(true, { status: 'active' })
    await handleSubscriptionDeleted(makeDeletedEvent())
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1)

    // Second invocation: status now 'canceled' → no-op, no additional write.
    installRunTxWithSnap(true, { status: 'canceled' })
    await handleSubscriptionDeleted(makeDeletedEvent())
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1) // still 1 across both
    const noopCalls = logSpy.mock.calls.filter((c) =>
      String(c[0]).includes('already canceled — no-op:'),
    )
    expect(noopCalls).toHaveLength(1)
  })
})
