import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('server-only', () => ({}))

import type Stripe from 'stripe'

import * as webhooks from './webhooks'

function makeEvent(type: string, id = 'evt_test_1'): Stripe.Event {
  return { id, type } as unknown as Stripe.Event
}

describe('routeEvent', () => {
  let invoicePaidSpy: ReturnType<typeof vi.spyOn>
  let subscriptionDeletedSpy: ReturnType<typeof vi.spyOn>
  let paymentFailedSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    invoicePaidSpy = vi.spyOn(webhooks, 'handleInvoicePaid').mockResolvedValue()
    subscriptionDeletedSpy = vi.spyOn(webhooks, 'handleSubscriptionDeleted').mockResolvedValue()
    paymentFailedSpy = vi.spyOn(webhooks, 'handlePaymentFailed').mockResolvedValue()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('dispatches invoice.paid to handleInvoicePaid only', async () => {
    const event = makeEvent('invoice.paid')
    await webhooks.routeEvent(event)
    expect(invoicePaidSpy).toHaveBeenCalledTimes(1)
    expect(invoicePaidSpy).toHaveBeenCalledWith(event)
    expect(subscriptionDeletedSpy).not.toHaveBeenCalled()
    expect(paymentFailedSpy).not.toHaveBeenCalled()
  })

  it('dispatches customer.subscription.deleted to handleSubscriptionDeleted only', async () => {
    const event = makeEvent('customer.subscription.deleted')
    await webhooks.routeEvent(event)
    expect(subscriptionDeletedSpy).toHaveBeenCalledTimes(1)
    expect(subscriptionDeletedSpy).toHaveBeenCalledWith(event)
    expect(invoicePaidSpy).not.toHaveBeenCalled()
    expect(paymentFailedSpy).not.toHaveBeenCalled()
  })

  it('dispatches invoice.payment_failed to handlePaymentFailed only', async () => {
    const event = makeEvent('invoice.payment_failed')
    await webhooks.routeEvent(event)
    expect(paymentFailedSpy).toHaveBeenCalledTimes(1)
    expect(paymentFailedSpy).toHaveBeenCalledWith(event)
    expect(invoicePaidSpy).not.toHaveBeenCalled()
    expect(subscriptionDeletedSpy).not.toHaveBeenCalled()
  })

  it('swallows unhandled event types without throwing and without calling handlers', async () => {
    const event = makeEvent('charge.succeeded')
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
    await expect(webhooks.routeEvent(event)).resolves.toBeUndefined()
    expect(invoicePaidSpy).not.toHaveBeenCalled()
    expect(subscriptionDeletedSpy).not.toHaveBeenCalled()
    expect(paymentFailedSpy).not.toHaveBeenCalled()
    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining('[webhooks/stripe'),
      'charge.succeeded',
    )
    logSpy.mockRestore()
  })

  it('re-throws errors from delegated handlers (route-level catch is the single swallow point)', async () => {
    invoicePaidSpy.mockRejectedValueOnce(new Error('boom'))
    const event = makeEvent('invoice.paid')
    await expect(webhooks.routeEvent(event)).rejects.toThrow('boom')
    expect(invoicePaidSpy).toHaveBeenCalledTimes(1)
    expect(invoicePaidSpy).toHaveBeenCalledWith(event)
  })
})
