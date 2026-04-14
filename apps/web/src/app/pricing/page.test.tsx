import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

import PricingPage, { metadata } from './page'

describe('Pricing Page', () => {
  it('renders a single h1 with the pricing headline', () => {
    render(<PricingPage />)
    const h1s = screen.getAllByRole('heading', { level: 1 })
    expect(h1s).toHaveLength(1)
    expect(h1s[0]).toHaveTextContent(/simple, honest pricing/i)
  })

  it('renders both plan cards with headings', () => {
    render(<PricingPage />)
    expect(screen.getByRole('heading', { level: 3, name: /monthly/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: /yearly/i })).toBeInTheDocument()
  })

  it('shows both prices formatted as euros with period labels', () => {
    render(<PricingPage />)
    const monthlyCard = screen.getByRole('article', { name: /monthly/i })
    const yearlyCard = screen.getByRole('article', { name: /yearly/i })
    expect(monthlyCard).toHaveTextContent(/€\s*7[.,]99/)
    expect(monthlyCard).toHaveTextContent('/month')
    expect(yearlyCard).toHaveTextContent(/€\s*79[.,]90/)
    expect(yearlyCard).toHaveTextContent('/year')
  })

  it('shows a derived savings label on the yearly card', () => {
    render(<PricingPage />)
    const savings = screen.getByTestId('savings-label')
    expect(savings).toHaveTextContent(/save/i)
    expect(savings).toHaveTextContent(/€\s*15[.,]98/)
    expect(savings).toHaveTextContent(/17%/)
  })

  it('shows a Best value badge on the yearly card only', () => {
    render(<PricingPage />)
    const yearlyCard = screen.getByRole('article', { name: /yearly/i })
    const monthlyCard = screen.getByRole('article', { name: /monthly/i })
    expect(yearlyCard).toHaveTextContent(/best value/i)
    expect(monthlyCard).not.toHaveTextContent(/best value/i)
  })

  it('renders both CTA buttons with the correct labels', () => {
    render(<PricingPage />)
    expect(screen.getByRole('button', { name: /subscribe monthly/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /subscribe yearly/i })).toBeInTheDocument()
  })

  it('CTA buttons are inert (disabled + no handler, no navigation or fetch surface)', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response())
    render(<PricingPage />)

    const monthlyCta = screen.getByRole('button', { name: /subscribe monthly/i })
    const yearlyCta = screen.getByRole('button', { name: /subscribe yearly/i })

    for (const cta of [monthlyCta, yearlyCta]) {
      expect(cta).toBeDisabled()
      expect(cta).toHaveAttribute('aria-disabled', 'true')
      expect(cta).toHaveAttribute('type', 'button')
      // No checkout-shaped escape hatches: no anchor wrapping, no formAction, no href
      expect(cta.closest('a')).toBeNull()
      expect(cta).not.toHaveAttribute('formaction')
      expect(cta).not.toHaveAttribute('href')
      // fireEvent.click bypasses jsdom's pointer-events-on-disabled guard that
      // userEvent enforces, so this would actually catch a wired-up onClick.
      fireEvent.click(cta)
    }

    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('uses semantic section elements and proper landmarks', () => {
    const { container } = render(<PricingPage />)
    const sections = container.querySelectorAll('section')
    expect(sections.length).toBeGreaterThanOrEqual(2)
    const articles = container.querySelectorAll('article')
    expect(articles).toHaveLength(2)
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
