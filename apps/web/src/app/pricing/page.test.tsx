import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

import PricingPage, { metadata } from './page'

vi.mock('@/components/checkout/PlanCta', () => ({
  PlanCta: ({ plan }: { plan: { id: string; name: string } }) => (
    <button type="button" data-testid={`plan-cta-${plan.id}`}>
      Subscribe {plan.name.toLowerCase()}
    </button>
  ),
}))

async function renderPricing(searchParams?: { checkout?: string }) {
  const ui = await PricingPage({
    searchParams: searchParams ? Promise.resolve(searchParams) : undefined,
  })
  return render(ui)
}

describe('Pricing Page', () => {
  it('renders a single h1 with the pricing headline', async () => {
    await renderPricing()
    const h1s = screen.getAllByRole('heading', { level: 1 })
    expect(h1s).toHaveLength(1)
    expect(h1s[0]).toHaveTextContent(/simple, honest pricing/i)
  })

  it('renders both plan cards with headings', async () => {
    await renderPricing()
    expect(screen.getByRole('heading', { level: 3, name: /monthly/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: /yearly/i })).toBeInTheDocument()
  })

  it('shows both prices formatted as euros with period labels', async () => {
    await renderPricing()
    const monthlyCard = screen.getByRole('article', { name: /monthly/i })
    const yearlyCard = screen.getByRole('article', { name: /yearly/i })
    expect(monthlyCard).toHaveTextContent(/€\s*7[.,]99/)
    expect(monthlyCard).toHaveTextContent('/month')
    expect(yearlyCard).toHaveTextContent(/€\s*79[.,]90/)
    expect(yearlyCard).toHaveTextContent('/year')
  })

  it('shows a derived savings label on the yearly card', async () => {
    await renderPricing()
    const savings = screen.getByTestId('savings-label')
    expect(savings).toHaveTextContent(/save/i)
    expect(savings).toHaveTextContent(/€\s*15[.,]98/)
    expect(savings).toHaveTextContent(/17%/)
  })

  it('shows a Best value badge on the yearly card only', async () => {
    await renderPricing()
    const yearlyCard = screen.getByRole('article', { name: /yearly/i })
    const monthlyCard = screen.getByRole('article', { name: /monthly/i })
    expect(yearlyCard).toHaveTextContent(/best value/i)
    expect(monthlyCard).not.toHaveTextContent(/best value/i)
  })

  it('renders PlanCta components for both plans', async () => {
    await renderPricing()
    expect(screen.getByTestId('plan-cta-monthly')).toBeInTheDocument()
    expect(screen.getByTestId('plan-cta-yearly')).toBeInTheDocument()
  })

  it('uses semantic section elements and proper landmarks', async () => {
    const { container } = await renderPricing()
    const sections = container.querySelectorAll('section')
    expect(sections.length).toBeGreaterThanOrEqual(2)
    const articles = container.querySelectorAll('article')
    expect(articles).toHaveLength(2)
  })

  it('renders the canceled banner when searchParams.checkout === "canceled"', async () => {
    await renderPricing({ checkout: 'canceled' })
    expect(screen.getByTestId('checkout-canceled-banner')).toHaveTextContent(/checkout canceled/i)
  })

  it('does not render the canceled banner without the query param', async () => {
    await renderPricing()
    expect(screen.queryByTestId('checkout-canceled-banner')).toBeNull()
  })

  it('exports metadata with Pricing title and openGraph block', () => {
    expect(metadata.title).toBe('Pricing — Warden')
    expect(metadata.description).toMatch(/pricing/i)
    expect(metadata.openGraph).toMatchObject({
      type: 'website',
      siteName: 'Warden',
    })
  })
})
