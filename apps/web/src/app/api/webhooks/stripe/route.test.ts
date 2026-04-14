import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('server-only', () => ({}))

const mockConstructEvent = vi.fn()

vi.mock('stripe', () => {
  function Stripe(this: { webhooks: unknown }) {
    this.webhooks = {
      constructEvent: (...args: unknown[]) => mockConstructEvent(...args),
    }
  }
  return { default: Stripe }
})

const mockTxGet = vi.fn()
const mockTxCreate = vi.fn()
const mockTxSet = vi.fn()
const mockRunTransaction = vi.fn()
const mockDocRef = { __ref: true }
const mockDoc = vi.fn(() => mockDocRef)
const mockCollection = vi.fn(() => ({ doc: mockDoc }))

vi.mock('@/lib/firebase/admin', () => ({
  adminDb: {
    collection: (...args: unknown[]) => mockCollection(...args),
    runTransaction: (...args: unknown[]) => mockRunTransaction(...args),
  },
}))

vi.mock('firebase-admin/firestore', () => ({
  FieldValue: {
    serverTimestamp: () => '__SERVER_TIMESTAMP__',
  },
}))

// Route tests verify the route's contract with routeEvent — the real dispatch
// (switch on event.type → handleX) is tested in webhooks.test.ts. Mocking
// routeEvent as a single vi.fn() keeps the two test suites non-overlapping.
const mockRouteEvent = vi.fn(async () => {})

vi.mock('@/lib/stripe/webhooks', () => ({
  routeEvent: (...args: unknown[]) => mockRouteEvent(...args),
}))

function makeEvent(type = 'invoice.paid', id = 'evt_test_123') {
  return {
    id,
    type,
    api_version: '2026-03-25.dahlia',
    livemode: false,
    data: { object: {} },
  }
}

type RequestLike = Request & { text: ReturnType<typeof vi.fn>; json: ReturnType<typeof vi.fn> }

function makeRequest(options: { body?: string; signature?: string | null }): RequestLike {
  const body = options.body ?? '{"id":"evt_test_123"}'
  const headers = new Headers()
  if (options.signature !== null && options.signature !== undefined) {
    headers.set('stripe-signature', options.signature)
  }
  const req = new Request('http://localhost/api/webhooks/stripe', {
    method: 'POST',
    headers,
    body,
  }) as RequestLike
  // Spy on .text() and .json() so tests can assert which one the handler uses.
  const textSpy = vi.fn(async () => body)
  const jsonSpy = vi.fn(async () => JSON.parse(body))
  Object.defineProperty(req, 'text', { value: textSpy })
  Object.defineProperty(req, 'json', { value: jsonSpy })
  return req
}

/**
 * Default runTransaction mock: invokes the callback with a fake tx whose
 * .get() resolves to the configured snapshot. Individual tests override.
 */
function installRunTransactionWithSnap(snap: { exists: boolean }) {
  mockRunTransaction.mockImplementation(async (cb: (tx: unknown) => unknown) => {
    const tx = {
      get: (...args: unknown[]) => {
        mockTxGet(...args)
        return Promise.resolve(snap)
      },
      create: (...args: unknown[]) => mockTxCreate(...args),
      set: (...args: unknown[]) => mockTxSet(...args),
    }
    return cb(tx)
  })
}

describe('POST /api/webhooks/stripe', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    vi.stubEnv('STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    vi.stubEnv('STRIPE_SECRET_KEY', 'sk_test_mock')
    installRunTransactionWithSnap({ exists: false })
    mockConstructEvent.mockImplementation(() => makeEvent('invoice.paid'))
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('signature OK + new event + routed type → 200, records event, routes handler', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { POST } = await import('./route')
    const req = makeRequest({ signature: 't=1,v1=abc' })
    const res = await POST(req)
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.data.duplicate).toBe(false)
    expect(body.data.eventType).toBe('invoice.paid')
    expect(body.data.eventId).toBe('evt_test_123')
    expect(mockTxCreate).toHaveBeenCalledTimes(1)
    expect(mockTxCreate.mock.calls[0][1]).toMatchObject({
      event_id: 'evt_test_123',
      event_type: 'invoice.paid',
      livemode: false,
      api_version: '2026-03-25.dahlia',
      received_at: '__SERVER_TIMESTAMP__',
    })
    // Guard the Anti-Pattern from the story: tx.set would silently overwrite duplicates.
    expect(mockTxSet).not.toHaveBeenCalled()
    expect(mockRouteEvent).toHaveBeenCalledTimes(1)
    expect(mockRouteEvent.mock.calls[0][0]).toMatchObject({
      id: 'evt_test_123',
      type: 'invoice.paid',
    })
    expect(errSpy).not.toHaveBeenCalled()
    errSpy.mockRestore()
  })

  it('signature OK + new event + unhandled type → 200, records, no handler call', async () => {
    mockConstructEvent.mockReturnValueOnce(makeEvent('charge.succeeded'))
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ signature: 't=1,v1=abc' }))
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.data.duplicate).toBe(false)
    expect(mockTxCreate).toHaveBeenCalledTimes(1)
    // routeEvent is still called for unhandled types — real routeEvent's
    // default branch swallows them (tested in webhooks.test.ts).
    expect(mockRouteEvent).toHaveBeenCalledTimes(1)
    expect(mockRouteEvent.mock.calls[0][0]).toMatchObject({ type: 'charge.succeeded' })
  })

  it('signature OK + duplicate event → 200 duplicate: true, no create, no routing', async () => {
    installRunTransactionWithSnap({ exists: true })
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ signature: 't=1,v1=abc' }))
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body).toEqual({ data: { received: true, duplicate: true } })
    expect(mockTxCreate).not.toHaveBeenCalled()
    expect(mockRouteEvent).not.toHaveBeenCalled()
    expect(logSpy).toHaveBeenCalledWith(
      '[webhooks/stripe] duplicate event skipped:',
      'evt_test_123',
    )
    logSpy.mockRestore()
  })

  it('race dedup (retry resolves to duplicate) → 200 duplicate: true, no routing', async () => {
    // Simulate the final, successful retry outcome: runTransaction resolves to `true`.
    mockRunTransaction.mockResolvedValueOnce(true)
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ signature: 't=1,v1=abc' }))
    expect(res.status).toBe(200)
    expect((await res.json()).data.duplicate).toBe(true)
    expect(mockRouteEvent).not.toHaveBeenCalled()
  })

  it('missing stripe-signature header → 400 INVALID_SIGNATURE, constructEvent not called', async () => {
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ signature: null }))
    expect(res.status).toBe(400)
    expect((await res.json()).error.code).toBe('INVALID_SIGNATURE')
    expect(mockConstructEvent).not.toHaveBeenCalled()
  })

  it('signature verification throws → 400 INVALID_SIGNATURE, logs, no Firestore touch', async () => {
    mockConstructEvent.mockImplementationOnce(() => {
      throw new Error('No signatures found matching the expected signature')
    })
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ signature: 't=1,v1=bad' }))
    expect(res.status).toBe(400)
    expect((await res.json()).error.code).toBe('INVALID_SIGNATURE')
    expect(errSpy).toHaveBeenCalledWith(
      '[webhooks/stripe] signature verification failed:',
      expect.any(Error),
    )
    expect(mockRunTransaction).not.toHaveBeenCalled()
    errSpy.mockRestore()
  })

  it('STRIPE_WEBHOOK_SECRET missing → 500 WEBHOOK_NOT_CONFIGURED, logs, constructEvent not called', async () => {
    vi.stubEnv('STRIPE_WEBHOOK_SECRET', '')
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ signature: 't=1,v1=abc' }))
    expect(res.status).toBe(500)
    expect((await res.json()).error.code).toBe('WEBHOOK_NOT_CONFIGURED')
    expect(errSpy).toHaveBeenCalledWith('[webhooks/stripe] STRIPE_WEBHOOK_SECRET is not set')
    expect(mockConstructEvent).not.toHaveBeenCalled()
    errSpy.mockRestore()
  })

  it('routing handler throws → 200 routingError: true, logs, dedup write still happened', async () => {
    mockRouteEvent.mockRejectedValueOnce(new Error('routing boom'))
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ signature: 't=1,v1=abc' }))
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.data.routingError).toBe(true)
    expect(body.data.eventId).toBe('evt_test_123')
    expect(mockTxCreate).toHaveBeenCalledTimes(1)
    expect(errSpy).toHaveBeenCalledWith(
      '[webhooks/stripe] routing failed for event:',
      'evt_test_123',
      'invoice.paid',
      expect.any(Error),
    )
    errSpy.mockRestore()
  })

  it('runTransaction throws → 200 routingError: true, logs, no routing call (AC #3)', async () => {
    // Firestore failure that escapes the transaction falls through to the
    // top-level catch, which returns 200 routingError:true so Stripe stops
    // retrying and an operator can replay from stripe_events later.
    mockRunTransaction.mockRejectedValueOnce(new Error('firestore unavailable'))
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { POST } = await import('./route')
    const res = await POST(makeRequest({ signature: 't=1,v1=abc' }))
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.data.routingError).toBe(true)
    expect(body.data.eventId).toBe('evt_test_123')
    expect(mockRouteEvent).not.toHaveBeenCalled()
    expect(errSpy).toHaveBeenCalledWith(
      '[webhooks/stripe] routing failed for event:',
      'evt_test_123',
      'invoice.paid',
      expect.any(Error),
    )
    errSpy.mockRestore()
  })

  it('reads raw body via .text(), never .json() (signature byte-for-byte)', async () => {
    const { POST } = await import('./route')
    const req = makeRequest({ signature: 't=1,v1=abc', body: '{"id":"evt_raw_bytes"}' })
    await POST(req)
    expect(req.text).toHaveBeenCalledTimes(1)
    expect(req.json).not.toHaveBeenCalled()
    // constructEvent must receive the exact raw text body.
    expect(mockConstructEvent.mock.calls[0][0]).toBe('{"id":"evt_raw_bytes"}')
    expect(mockConstructEvent.mock.calls[0][1]).toBe('t=1,v1=abc')
    expect(mockConstructEvent.mock.calls[0][2]).toBe('whsec_test_secret')
  })
})
