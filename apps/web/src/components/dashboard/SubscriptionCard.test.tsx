import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

import { SubscriptionCard } from './SubscriptionCard'
import type { SubscriptionResponse } from '@/lib/schemas/subscription'

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const activeSubscription: SubscriptionResponse = {
  status: 'active',
  plan: 'monthly',
  current_period_end: 1735689600,
  stripe_customer_id: 'cus_abc',
  stripe_subscription_id: 'sub_abc',
}

describe('SubscriptionCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders skeleton components in loading state', () => {
    render(
      <SubscriptionCard
        subscription={null}
        loading={true}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
  })

  it('displays active subscription with green badge', () => {
    render(
      <SubscriptionCard
        subscription={activeSubscription}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(screen.getByText('test@example.com')).toBeDefined()
    expect(screen.getByText('Monthly')).toBeDefined()
    expect(screen.getByText('Active')).toBeDefined()
    const badge = screen.getByText('Active')
    expect(badge.className).toContain('green')
    expect(screen.getByText('Next payment')).toBeDefined()
  })

  it('displays past_due subscription with amber badge', () => {
    const sub: SubscriptionResponse = { ...activeSubscription, status: 'past_due' }
    render(
      <SubscriptionCard
        subscription={sub}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(screen.getByText('Past due')).toBeDefined()
    const badge = screen.getByText('Past due')
    expect(badge.className).toContain('amber')
    expect(screen.getByText('Payment due')).toBeDefined()
  })

  it('displays canceled subscription with muted badge and "Access until" label', () => {
    const sub: SubscriptionResponse = { ...activeSubscription, status: 'canceled' }
    render(
      <SubscriptionCard
        subscription={sub}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(screen.getByText('Canceled')).toBeDefined()
    expect(screen.getByText('Access until')).toBeDefined()
  })

  it('displays no-subscription state with pricing link', () => {
    render(
      <SubscriptionCard
        subscription={null}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(screen.getByText('test@example.com')).toBeDefined()
    expect(screen.getByText('No active subscription')).toBeDefined()
    const link = screen.getByText('View plans')
    expect(link.closest('a')).toHaveAttribute('href', '/pricing')
  })

  it('displays error state with Try again button and email', () => {
    render(
      <SubscriptionCard
        subscription={null}
        loading={false}
        error="Unable to load subscription data"
        userEmail="test@example.com"
      />,
    )
    expect(screen.getByText('test@example.com')).toBeDefined()
    expect(screen.getByText('Unable to load subscription data')).toBeDefined()
    expect(screen.getByText('Try again')).toBeDefined()
  })

  it('formats date from Unix seconds', () => {
    render(
      <SubscriptionCard
        subscription={activeSubscription}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(screen.getByText('1 January 2025')).toBeDefined()
  })

  it('always shows text alongside badge color (not color-only)', () => {
    render(
      <SubscriptionCard
        subscription={activeSubscription}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    const badge = screen.getByText('Active')
    expect(badge.textContent).toBe('Active')
  })

  // Portal button tests
  it('renders "Manage Subscription" button for active subscription', () => {
    render(
      <SubscriptionCard
        subscription={activeSubscription}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(screen.getByRole('button', { name: /manage subscription/i })).toBeDefined()
  })

  it('renders "Manage Subscription" button for past_due subscription', () => {
    const sub: SubscriptionResponse = { ...activeSubscription, status: 'past_due' }
    render(
      <SubscriptionCard
        subscription={sub}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(screen.getByRole('button', { name: /manage subscription/i })).toBeDefined()
  })

  it('renders "Manage Subscription" button for canceled subscription', () => {
    const sub: SubscriptionResponse = { ...activeSubscription, status: 'canceled' }
    render(
      <SubscriptionCard
        subscription={sub}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(screen.getByRole('button', { name: /manage subscription/i })).toBeDefined()
  })

  it('does not render "Manage Subscription" button in no-subscription state', () => {
    render(
      <SubscriptionCard
        subscription={null}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(screen.queryByRole('button', { name: /manage subscription/i })).toBeNull()
  })

  it('does not render "Manage Subscription" button in loading state', () => {
    render(
      <SubscriptionCard
        subscription={null}
        loading={true}
        error={null}
        userEmail="test@example.com"
      />,
    )
    expect(screen.queryByRole('button', { name: /manage subscription/i })).toBeNull()
  })

  it('does not render "Manage Subscription" button in error state', () => {
    render(
      <SubscriptionCard
        subscription={null}
        loading={false}
        error="Some error"
        userEmail="test@example.com"
      />,
    )
    expect(screen.queryByRole('button', { name: /manage subscription/i })).toBeNull()
  })

  it('shows loading text when portal button is clicked', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise(() => {})),
    )

    render(
      <SubscriptionCard
        subscription={activeSubscription}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )

    const button = screen.getByRole('button', { name: /manage subscription/i })
    fireEvent.click(button)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /loading/i })).toBeDefined()
    })
  })

  it('shows error text when portal API fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ error: { message: 'No subscription found to manage' } }),
      }),
    )

    render(
      <SubscriptionCard
        subscription={activeSubscription}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )

    const button = screen.getByRole('button', { name: /manage subscription/i })
    fireEvent.click(button)

    await waitFor(() => {
      expect(screen.getByText('No subscription found to manage')).toBeDefined()
    })
  })
})
