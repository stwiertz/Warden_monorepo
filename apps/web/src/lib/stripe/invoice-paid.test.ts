import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('server-only', () => ({}))

// Plain-function Stripe constructor (Epic 3 retro #3 — the Vitest v4 ES-module gotcha).
vi.mock('stripe', () => {
  function Stripe(this: Record<string, unknown>) {
    this.subscriptions = {}
  }
  return { default: Stripe }
})

// Hoisted state so the mock factories below can see mutable refs.
const mocks = vi.hoisted(() => {
  class FakeTimestamp {
    constructor(public readonly millis: number) {}
    static fromMillis(ms: number) {
      return new FakeTimestamp(ms)
    }
  }
  const mockSubRetrieve = vi.fn()
  const mockTxGet = vi.fn()
  const mockTxCreate = vi.fn()
  const mockTxUpdate = vi.fn()
  const mockTxSet = vi.fn()
  const mockRunTransaction = vi.fn()
  const mockDocRef = { __ref: true } as unknown
  const mockDoc = vi.fn(() => mockDocRef)
  const mockCollection = vi.fn(() => ({ doc: mockDoc }))
  return {
    FakeTimestamp,
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

const FakeTimestamp = mocks.FakeTimestamp

vi.mock('firebase-admin/firestore', () => ({
  FieldValue: {
    serverTimestamp: () => '__SERVER_TIMESTAMP__',
  },
  Timestamp: mocks.FakeTimestamp,
}))

vi.mock('@/lib/firebase/admin', () => ({
  adminDb: {
    collection: (...args: unknown[]) => mocks.mockCollection(...args),
    runTransaction: (...args: unknown[]) => mocks.mockRunTransaction(...args),
  },
}))

// Preserve the real retryStripeCall; only swap getStripe.
vi.mock('@/lib/stripe/server', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/stripe/server')>()
  return {
    ...actual,
    getStripe: () => ({ subscriptions: { retrieve: mocks.mockSubRetrieve } }),
  }
})

// IMPORTANT: import AFTER all mocks are registered.
import { handleInvoicePaid } from '@/lib/stripe/webhooks'

type InvoiceShape = {
  customer: string
  parent: { subscription_details: { subscription: string } }
  lines: { data: Array<{ period: { end: number } }> }
}

function makeInvoice(overrides: Partial<InvoiceShape> = {}): InvoiceShape {
  return {
    customer: 'cus_test_123',
    parent: { subscription_details: { subscription: 'sub_test_123' } },
    lines: {
      data: [{ period: { end: 1_800_000_000 } }],
    },
    ...overrides,
  }
}

function makeEvent(invoiceOverrides: Partial<InvoiceShape> = {}, id = 'evt_ip_1') {
  return {
    id,
    type: 'invoice.paid',
    data: { object: makeInvoice(invoiceOverrides) },
  } as unknown as import('stripe').Stripe.Event
}

function installRunTxWithSnap(exists: boolean) {
  mocks.mockRunTransaction.mockImplementation(async (cb: (tx: unknown) => unknown) => {
    const tx = {
      get: (...args: unknown[]) => {
        mocks.mockTxGet(...args)
        return Promise.resolve({ exists })
      },
      create: (...args: unknown[]) => mocks.mockTxCreate(...args),
      update: (...args: unknown[]) => mocks.mockTxUpdate(...args),
      set: (...args: unknown[]) => mocks.mockTxSet(...args),
    }
    return cb(tx)
  })
}

describe('handleInvoicePaid', () => {
  let errSpy: ReturnType<typeof vi.spyOn>
  let logSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.clearAllMocks()
    installRunTxWithSnap(false)
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

  it('happy path, new user (create branch) — monthly', async () => {
    await handleInvoicePaid(makeEvent())
    expect(mocks.mockSubRetrieve).toHaveBeenCalledTimes(1)
    expect(mocks.mockSubRetrieve).toHaveBeenCalledWith('sub_test_123')
    expect(mocks.mockCollection).toHaveBeenCalledWith('users')
    expect(mocks.mockDoc).toHaveBeenCalledWith('uid_abc')
    expect(mocks.mockTxCreate).toHaveBeenCalledTimes(1)
    const [ref, fields] = mocks.mockTxCreate.mock.calls[0]
    expect(ref).toBe(mocks.mockDocRef)
    expect(fields).toMatchObject({
      status: 'active',
      plan: 'monthly',
      stripe_subscription_id: 'sub_test_123',
      stripe_customer_id: 'cus_test_123',
      updated_at: '__SERVER_TIMESTAMP__',
      created_at: '__SERVER_TIMESTAMP__',
    })
    expect(fields.current_period_end).toBeInstanceOf(FakeTimestamp)
    expect(mocks.mockTxUpdate).not.toHaveBeenCalled()
    expect(mocks.mockTxSet).not.toHaveBeenCalled()
  })

  it('happy path, existing user (update branch)', async () => {
    installRunTxWithSnap(true)
    await handleInvoicePaid(makeEvent())
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1)
    const [, fields] = mocks.mockTxUpdate.mock.calls[0]
    expect(fields).toMatchObject({
      status: 'active',
      plan: 'monthly',
      stripe_subscription_id: 'sub_test_123',
      stripe_customer_id: 'cus_test_123',
      updated_at: '__SERVER_TIMESTAMP__',
    })
    expect('created_at' in fields).toBe(false)
    expect(mocks.mockTxCreate).not.toHaveBeenCalled()
    expect(mocks.mockTxSet).not.toHaveBeenCalled()
  })

  it('yearly plan', async () => {
    mocks.mockSubRetrieve.mockResolvedValueOnce({
      id: 'sub_test_123',
      customer: 'cus_test_123',
      metadata: { firebase_uid: 'uid_abc', plan_id: 'yearly' },
    })
    installRunTxWithSnap(true)
    await handleInvoicePaid(makeEvent())
    const [, fields] = mocks.mockTxUpdate.mock.calls[0]
    expect(fields.plan).toBe('yearly')
  })

  it('Zod schema failure — throws, no retrieve, no runTransaction', async () => {
    const badEvent = {
      id: 'evt_bad',
      type: 'invoice.paid',
      // parent.subscription_details.subscription missing — triggers schema failure.
      data: {
        object: {
          customer: 'cus_1',
          parent: { subscription_details: {} },
          lines: { data: [{ period: { end: 1 } }] },
        },
      },
    } as unknown as import('stripe').Stripe.Event
    await expect(handleInvoicePaid(badEvent)).rejects.toThrow(/schema validation/)
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('[webhooks/stripe'),
      expect.anything(),
      'evt_bad',
    )
    expect(mocks.mockSubRetrieve).not.toHaveBeenCalled()
    expect(mocks.mockRunTransaction).not.toHaveBeenCalled()
  })

  it('subscription missing firebase_uid metadata — throws, no runTransaction', async () => {
    mocks.mockSubRetrieve.mockResolvedValueOnce({
      id: 'sub_test_123',
      customer: 'cus_test_123',
      metadata: {},
    })
    await expect(handleInvoicePaid(makeEvent())).rejects.toThrow(/firebase_uid/)
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('[webhooks/stripe'),
      'evt_ip_1',
      'sub_test_123',
    )
    expect(mocks.mockRunTransaction).not.toHaveBeenCalled()
  })

  it('subscription has unknown plan_id — throws, no runTransaction', async () => {
    mocks.mockSubRetrieve.mockResolvedValueOnce({
      id: 'sub_test_123',
      customer: 'cus_test_123',
      metadata: { firebase_uid: 'uid_x', plan_id: 'enterprise' },
    })
    await expect(handleInvoicePaid(makeEvent())).rejects.toThrow(/unknown plan_id/)
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('[webhooks/stripe'),
      'evt_ip_1',
      'enterprise',
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
      const promise = handleInvoicePaid(makeEvent())
      // Drain the first rejection microtask without tripping the 250ms backoff.
      await vi.advanceTimersByTimeAsync(249)
      expect(mocks.mockSubRetrieve).toHaveBeenCalledTimes(1)
      // Cross the 250ms boundary — the second attempt should now fire.
      await vi.advanceTimersByTimeAsync(2)
      await promise
    } finally {
      vi.useRealTimers()
    }
    expect(mocks.mockSubRetrieve).toHaveBeenCalledTimes(2)
    expect(mocks.mockRunTransaction).toHaveBeenCalledTimes(1)
    expect(mocks.mockTxCreate).toHaveBeenCalledTimes(1)
  })

  it('Firestore transaction retries re-read users/{uid} inside the closure (AC #7)', async () => {
    // Simulate Firestore's own ABORTED retry: the SDK invokes the callback twice.
    // First invocation sees exists:false (would create), second sees exists:true
    // (must update). If snap were hoisted outside the closure, the second invocation
    // would still take the create branch — which is the regression this test guards.
    const snapSequence = [false, true]
    mocks.mockRunTransaction.mockImplementation(async (cb: (tx: unknown) => unknown) => {
      let result: unknown
      for (const exists of snapSequence) {
        const tx = {
          get: (...args: unknown[]) => {
            mocks.mockTxGet(...args)
            return Promise.resolve({ exists })
          },
          create: (...args: unknown[]) => mocks.mockTxCreate(...args),
          update: (...args: unknown[]) => mocks.mockTxUpdate(...args),
          set: (...args: unknown[]) => mocks.mockTxSet(...args),
        }
        result = await cb(tx)
      }
      return result
    })

    await handleInvoicePaid(makeEvent())

    // tx.get must be called on EACH retry attempt — proof snap is inside the closure.
    expect(mocks.mockTxGet).toHaveBeenCalledTimes(2)
    // Final branch reflects the SECOND attempt's snap (exists:true → update).
    expect(mocks.mockTxUpdate).toHaveBeenCalledTimes(1)
    // The first attempt's create also fired (tx.create is a no-op here because
    // the fake tx doesn't enforce terminal state), but the terminal write is update.
    expect(mocks.mockTxSet).not.toHaveBeenCalled()
  })

  it('non-transient Stripe error NOT retried', async () => {
    const badReq = Object.assign(new Error('invalid'), {
      type: 'StripeInvalidRequestError',
      statusCode: 400,
    })
    mocks.mockSubRetrieve.mockRejectedValueOnce(badReq)
    await expect(handleInvoicePaid(makeEvent())).rejects.toThrow(/invalid/)
    expect(mocks.mockSubRetrieve).toHaveBeenCalledTimes(1)
    expect(mocks.mockRunTransaction).not.toHaveBeenCalled()
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('[webhooks/stripe'),
      'evt_ip_1',
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
      const promise = handleInvoicePaid(makeEvent()).catch((e) => {
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
    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining('[webhooks/stripe'),
      'evt_ip_1',
      'sub_test_123',
      connErr,
    )
  })

  it('Firestore transaction throws — handler propagates', async () => {
    mocks.mockRunTransaction.mockRejectedValueOnce(new Error('permission-denied'))
    await expect(handleInvoicePaid(makeEvent())).rejects.toThrow('permission-denied')
  })

  it('period_end is written as a Timestamp, not a number', async () => {
    await handleInvoicePaid(makeEvent())
    const [, fields] = mocks.mockTxCreate.mock.calls[0]
    expect(fields.current_period_end).toBeInstanceOf(FakeTimestamp)
    expect(fields.current_period_end.millis).toBe(1_800_000_000 * 1000)
  })

  it('stripe_customer_id is coerced to string when customer comes back as object', async () => {
    mocks.mockSubRetrieve.mockResolvedValueOnce({
      id: 'sub_test_123',
      customer: { id: 'cus_obj' },
      metadata: { firebase_uid: 'uid_abc', plan_id: 'monthly' },
    })
    await handleInvoicePaid(makeEvent())
    const [, fields] = mocks.mockTxCreate.mock.calls[0]
    expect(fields.stripe_customer_id).toBe('cus_obj')
  })
})
