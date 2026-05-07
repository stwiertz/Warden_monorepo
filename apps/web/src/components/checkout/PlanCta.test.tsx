import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { PlanCta } from './PlanCta'
import { CheckoutProvider, type AppliedCoupon } from './CheckoutContext'
import { PLAN_MONTHLY } from '@/lib/pricing/plans'

const mockPush = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

let authState: { user: unknown; loading: boolean } = { user: { uid: 'u1' }, loading: false }

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => authState,
}))

const mockAssign = vi.fn()
const originalLocation = window.location

function renderCta(initialCoupon?: AppliedCoupon) {
  return render(
    <CheckoutProvider initialCoupon={initialCoupon}>
      <PlanCta plan={PLAN_MONTHLY} />
    </CheckoutProvider>,
  )
}

describe('PlanCta', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState = { user: { uid: 'u1' }, loading: false }
    mockAssign.mockReset()
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: Object.assign({}, originalLocation, { assign: mockAssign }),
    })
  })

  afterAll(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: originalLocation,
    })
  })

  it('renders an enabled button for an authenticated user', () => {
    renderCta()
    const btn = screen.getByRole('button', { name: /subscribe monthly/i })
    expect(btn).toBeEnabled()
  })

  it('renders a disabled button while auth is loading', () => {
    authState = { user: null, loading: true }
    renderCta()
    expect(screen.getByRole('button', { name: /subscribe monthly/i })).toBeDisabled()
  })

  it('redirects unauthenticated users to sign-in with next=/pricing', async () => {
    authState = { user: null, loading: false }
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    renderCta()
    await userEvent.click(screen.getByRole('button', { name: /subscribe monthly/i }))
    expect(mockPush).toHaveBeenCalledWith('/auth/sign-in?next=/pricing')
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('authenticated click POSTs to /api/checkout/session and redirects to url on success', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ data: { url: 'https://checkout.stripe.com/c/pay/mock' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    renderCta()
    await userEvent.click(screen.getByRole('button', { name: /subscribe monthly/i }))

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/checkout/session',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ planId: 'monthly' }),
      }),
    )
    await waitFor(() => {
      expect(mockAssign).toHaveBeenCalledWith('https://checkout.stripe.com/c/pay/mock')
    })
    fetchSpy.mockRestore()
  })

  it('shows an error alert and re-enables the button when API responds 500', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'CHECKOUT_FAILED', message: 'boom' } }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    renderCta()
    const btn = screen.getByRole('button', { name: /subscribe monthly/i })
    await userEvent.click(btn)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/something went wrong/i)
    expect(btn).toBeEnabled()
    expect(mockAssign).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('shows an error alert on network error', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'))
    renderCta()
    await userEvent.click(screen.getByRole('button', { name: /subscribe monthly/i }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/something went wrong/i)
    fetchSpy.mockRestore()
  })

  it('with an applied coupon, includes couponCode in the request body', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ data: { url: 'https://checkout.stripe.com/c/pay/x' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    renderCta({
      code: 'HALF',
      percentOff: 50,
      amountOffCents: null,
      durationInMonths: null,
    })
    await userEvent.click(screen.getByRole('button', { name: /subscribe monthly/i }))
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/checkout/session',
      expect.objectContaining({
        body: JSON.stringify({ planId: 'monthly', couponCode: 'HALF' }),
      }),
    )
    fetchSpy.mockRestore()
  })

  it('on 400 COUPON_INVALID renders coupon-specific error and clears coupon', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'COUPON_INVALID', message: 'gone' } }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    function Probe() {
      return (
        <CheckoutProvider
          initialCoupon={{
            code: 'HALF',
            percentOff: 50,
            amountOffCents: null,
            durationInMonths: null,
          }}
        >
          <PlanCta plan={PLAN_MONTHLY} />
        </CheckoutProvider>
      )
    }
    render(<Probe />)
    await userEvent.click(screen.getByRole('button', { name: /subscribe monthly/i }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/applied coupon is no longer valid/i)
  })
})
