import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('server-only', () => ({}))

vi.mock('stripe', () => {
  function Stripe(this: Record<string, unknown>) {
    this.subscriptions = {}
  }
  return { default: Stripe }
})

const mocks = vi.hoisted(() => {
  const mockSubRetrieve = vi.fn()
  const mockTxGet = vi.fn()
  const mockTxCreate = vi.fn()
  const mockTxUpdate = vi.fn()
  const mockTxSet = vi.fn()
  const mockRunTransaction = vi.fn()
  const mockDocRef = { __ref: true } as unknown
  const mockDoc = vi.fn(() => mockDocRef)
  const mockCollection = vi.fn((..._args: unknown[]) => ({ doc: mockDoc }))
  return {
    mockSubRetrieve,
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

// Preserve real retryStripeCall (Story 4.2 pattern); only swap getStripe.
vi.mock('@/lib/stripe/server', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/stripe/server')>()
  return {
    ...actual,
    getStripe: () => ({ subscriptions: { retrieve: mocks.mockSubRetrieve } }),
  }
})

import { handlePaymentFailed } from '@/lib/stripe/webhooks'
import type Stripe from 'stripe'

type InvoiceShape = {
  customer: string
  parent: { subscription_details: { subscription: string } }
}

function makeInvoice(overrides: Partial<InvoiceShape> = {}): InvoiceShape {
  return {
    customer: 'cus_test_123',
    parent: { subscription_details: { subscription: 'sub_test_123' } },
    ...overrides,
  }
}

function makeFailedEvent(
  invoiceOverrides: Partial<InvoiceShape> = {},
  id = 'evt_pf_1',
): Stripe.Event {
  return {
    id,
    type: 'invoice.payment_failed',
    data: { object: makeInvoice(invoiceOverrides) },
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

describe('handlePaymentFailed', () => {
  let errSpy: ReturnType<typeof vi.spyOn>
  let logSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.clearAllMocks()
    installRunTxWithSnap(true, { status: 'active', plan: 'monthly' })
    mocks.mockSubRetrieve.mockResolvedValue({
      id: 'sub_test_123',
      customer: 'cus_test_123',
      metadata: { firebase_uid: 'uid_abc', plan_id: 'monthly' },
    })
    errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    logSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
  })

  afterEach(() => {
    errSpy.mockRestore()
    logSpy.mockRestore()
    vi.unstubAllEnvs()
  })

  it('happy path — active user → past_due, minimal field bag', async () => {
    await handlePaymentFailed(makeFailedEvent())
    expect(mocks.mockSubRetrieve).toHaveBeenCalledWith('sub_test_123')
    expect(mocks.mockCollection).toHaveBeenCalledWith('users')
    expect(mocks.mockDoc).toHaveBeenCalledWith('uid_abc')
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1)
    const [, fields] = mocks.mockTxUpdate.mock.calls[0]
    expect(Object.keys(fields).sort()).toEqual(['status', 'updated_at'])
    expect(fields.status).toBe('past_due')
    expect(fields.updated_at).toBe('__SERVER_TIMESTAMP__')
    expect(mocks.mockTxCreate).not.toHaveBeenCalled()
    expect(mocks.mockTxSet).not.toHaveBeenCalled()
    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining('invoice.payment_failed processed:'),
      'evt_pf_1',
      'uid_abc',
      'sub_test_123',
    )
  })

  it('idempotent no-op — already past_due', async () => {
    installRunTxWithSnap(true, { status: 'past_due' })
    await handlePaymentFailed(makeFailedEvent())
    expect(mocks.mockTxUpdate).not.toHaveBeenCalled()
    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining('already past_due — no-op:'),
      'evt_pf_1',
      'uid_abc',
    )
  })

  it('skip — user already canceled (do NOT resurrect)', async () => {
    installRunTxWithSnap(true, { status: 'canceled' })
    await handlePaymentFailed(makeFailedEvent())
    expect(mocks.mockTxUpdate).not.toHaveBeenCalled()
    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining('skipped — user already canceled:'),
      'evt_pf_1',
      'uid_abc',
    )
  })

  it('user doc missing — throws, no write', async () => {
    installRunTxWithSnap(false)
    await expect(handlePaymentFailed(makeFailedEvent())).rejects.toThrow(/user document not found/)
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('user document not found — cannot update subscription state:'),
      'evt_pf_1',
      'uid_abc',
    )
    expect(mocks.mockTxUpdate).not.toHaveBeenCalled()
  })

  it('Zod schema failure — missing parent.subscription_details.subscription', async () => {
    const badEvent = {
      id: 'evt_bad',
      type: 'invoice.payment_failed',
      data: {
        object: {
          customer: 'cus_1',
          parent: { subscription_details: {} },
        },
      },
    } as unknown as Stripe.Event
    await expect(handlePaymentFailed(badEvent)).rejects.toThrow(/schema validation/)
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('payload failed schema validation:'),
      expect.anything(),
      'evt_bad',
    )
    expect(mocks.mockSubRetrieve).not.toHaveBeenCalled()
    expect(mocks.mockRunTransaction).not.toHaveBeenCalled()
  })

  it('missing firebase_uid on retrieved subscription — throws', async () => {
    mocks.mockSubRetrieve.mockResolvedValueOnce({
      id: 'sub_test_123',
      customer: 'cus_test_123',
      metadata: {},
    })
    await expect(handlePaymentFailed(makeFailedEvent())).rejects.toThrow(/firebase_uid/)
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('invoice.payment_failed subscription missing firebase_uid metadata'),
      'evt_pf_1',
      'sub_test_123',
    )
    expect(mocks.mockRunTransaction).not.toHaveBeenCalled()
  })

  it('transient Stripe error retried successfully (respects 250ms backoff boundary)', async () => {
    const connErr = Object.assign(new Error('conn reset'), {
      type: 'StripeConnectionError',
    })
    mocks.mockSubRetrieve.mockRejectedValueOnce(connErr).mockResolvedValueOnce({
      id: 'sub_test_123',
      customer: 'cus_test_123',
      metadata: { firebase_uid: 'uid_abc', plan_id: 'monthly' },
    })

    vi.useFakeTimers()
    try {
      const promise = handlePaymentFailed(makeFailedEvent())
      await vi.advanceTimersByTimeAsync(249)
      expect(mocks.mockSubRetrieve).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(2)
      await promise
    } finally {
      vi.useRealTimers()
    }
    expect(mocks.mockSubRetrieve).toHaveBeenCalledTimes(2)
    expect(mocks.mockRunTransaction).toHaveBeenCalledTimes(1)
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1)
  })

  it('non-transient Stripe error NOT retried', async () => {
    const badReq = Object.assign(new Error('invalid'), {
      type: 'StripeInvalidRequestError',
      statusCode: 400,
    })
    mocks.mockSubRetrieve.mockRejectedValueOnce(badReq)
    await expect(handlePaymentFailed(makeFailedEvent())).rejects.toThrow(/invalid/)
    expect(mocks.mockSubRetrieve).toHaveBeenCalledTimes(1)
    expect(mocks.mockRunTransaction).not.toHaveBeenCalled()
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('subscription retrieve failed after retries:'),
      'evt_pf_1',
      'sub_test_123',
      badReq,
    )
  })

  it('transient errors exhaust retry budget', async () => {
    const connErr = Object.assign(new Error('conn reset'), {
      type: 'StripeConnectionError',
    })
    mocks.mockSubRetrieve
      .mockRejectedValueOnce(connErr)
      .mockRejectedValueOnce(connErr)
      .mockRejectedValueOnce(connErr)

    vi.useFakeTimers()
    let thrown: unknown
    try {
      const promise = handlePaymentFailed(makeFailedEvent()).catch((e) => {
        thrown = e
      })
      await vi.advanceTimersByTimeAsync(2000)
      await promise
    } finally {
      vi.useRealTimers()
    }
    expect(thrown).toBe(connErr)
    expect(mocks.mockSubRetrieve).toHaveBeenCalledTimes(3)
    expect(mocks.mockRunTransaction).not.toHaveBeenCalled()
  })

  it('Firestore transaction throws — handler propagates', async () => {
    mocks.mockRunTransaction.mockRejectedValueOnce(new Error('aborted'))
    await expect(handlePaymentFailed(makeFailedEvent())).rejects.toThrow('aborted')
  })

  it('idempotent replay: second invocation (already past_due) is a no-op', async () => {
    // First invocation: active → past_due (write).
    installRunTxWithSnap(true, { status: 'active' })
    await handlePaymentFailed(makeFailedEvent())
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1)

    // Second invocation: status now past_due → no-op.
    installRunTxWithSnap(true, { status: 'past_due' })
    await handlePaymentFailed(makeFailedEvent())
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1)
    const noopCalls = logSpy.mock.calls.filter((c: unknown[]) =>
      String(c[0]).includes('already past_due — no-op:'),
    )
    expect(noopCalls).toHaveLength(1)
  })
})
