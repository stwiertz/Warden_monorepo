import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

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
    // 1735689600 = 1 Jan 2025 00:00:00 UTC
    render(
      <SubscriptionCard
        subscription={activeSubscription}
        loading={false}
        error={null}
        userEmail="test@example.com"
      />,
    )
    // en-GB long format: "1 January 2025"
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
})
