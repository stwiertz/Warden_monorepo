import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { CouponInput } from './CouponInput'
import { CheckoutProvider } from './CheckoutContext'

function renderWithProvider() {
  return render(
    <CheckoutProvider>
      <CouponInput />
    </CheckoutProvider>,
  )
}

describe('CouponInput', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders an input and an Apply button', () => {
    renderWithProvider()
    expect(screen.getByLabelText(/coupon code/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /apply/i })).toBeInTheDocument()
  })

  it('does nothing when submitting an empty input', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    renderWithProvider()
    await userEvent.click(screen.getByRole('button', { name: /apply/i }))
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('happy path POSTs and applies the coupon, showing a status message', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            code: 'SAVE50',
            percentOff: 50,
            amountOffCents: null,
            durationInMonths: null,
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    renderWithProvider()
    await userEvent.type(screen.getByLabelText(/coupon code/i), 'SAVE50')
    await userEvent.click(screen.getByRole('button', { name: /apply/i }))

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/checkout/coupon',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ code: 'SAVE50' }),
      }),
    )
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/coupon applied: SAVE50/i)
    })
    expect(screen.getByRole('button', { name: /remove/i })).toBeInTheDocument()
  })

  it('shows an inline error on 400 COUPON_INVALID without touching context', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'COUPON_INVALID', message: 'nope' } }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    renderWithProvider()
    await userEvent.type(screen.getByLabelText(/coupon code/i), 'BADCODE')
    await userEvent.click(screen.getByRole('button', { name: /apply/i }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/not valid or has expired/i)
    expect(screen.queryByRole('button', { name: /remove/i })).toBeNull()
  })

  it('shows a generic error on 500 COUPON_LOOKUP_FAILED', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'COUPON_LOOKUP_FAILED', message: 'down' } }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    renderWithProvider()
    await userEvent.type(screen.getByLabelText(/coupon code/i), 'X')
    await userEvent.click(screen.getByRole('button', { name: /apply/i }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/something went wrong/i)
  })

  it('shows a generic error on a network failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'))
    renderWithProvider()
    await userEvent.type(screen.getByLabelText(/coupon code/i), 'X')
    await userEvent.click(screen.getByRole('button', { name: /apply/i }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/something went wrong/i)
  })

  it('Enter inside the input submits the form', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { code: 'SAVE50', percentOff: 50, amountOffCents: null, durationInMonths: null },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    renderWithProvider()
    const input = screen.getByLabelText(/coupon code/i)
    await userEvent.type(input, 'SAVE50{Enter}')
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(1)
    })
  })

  it('disables the input when a coupon is already applied (initialCoupon)', () => {
    render(
      <CheckoutProvider
        initialCoupon={{
          code: 'PRESET',
          percentOff: 25,
          amountOffCents: null,
          durationInMonths: null,
        }}
      >
        <CouponInput />
      </CheckoutProvider>,
    )
    const input = screen.getByLabelText(/coupon code/i) as HTMLInputElement
    expect(input).toBeDisabled()
    expect(input.value).toBe('PRESET')
    expect(screen.getByRole('button', { name: /remove/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /apply/i })).toBeNull()
  })

  it('Remove button clears the coupon from context', async () => {
    render(
      <CheckoutProvider
        initialCoupon={{
          code: 'PRESET',
          percentOff: 25,
          amountOffCents: null,
          durationInMonths: null,
        }}
      >
        <CouponInput />
      </CheckoutProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: /remove/i }))
    expect(screen.getByRole('button', { name: /apply/i })).toBeInTheDocument()
    expect((screen.getByLabelText(/coupon code/i) as HTMLInputElement).value).toBe('')
  })
})
