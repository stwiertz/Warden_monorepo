import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Home, { metadata } from './page'

describe('Landing Page', () => {
  it('renders the hero section with h1 heading', () => {
    render(<Home />)
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toBeInTheDocument()
    expect(heading).toHaveTextContent(/better coaching starts with better review/i)
  })

  it('renders the features section with heading', () => {
    render(<Home />)
    expect(
      screen.getByRole('heading', { name: /everything you need to coach effectively/i }),
    ).toBeInTheDocument()
  })

  it('renders all four feature cards', () => {
    render(<Home />)
    expect(screen.getByText('Session Review')).toBeInTheDocument()
    expect(screen.getByText('Clip Export')).toBeInTheDocument()
    expect(screen.getByText('Minimap Analysis')).toBeInTheDocument()
    expect(screen.getByText('Coaching Workflows')).toBeInTheDocument()
  })

  it('renders the download section with heading', () => {
    render(<Home />)
    expect(screen.getByRole('heading', { name: /get the warden app/i })).toBeInTheDocument()
  })

  it('renders the pricing CTA section with heading', () => {
    render(<Home />)
    expect(
      screen.getByRole('heading', { name: /start coaching smarter today/i }),
    ).toBeInTheDocument()
  })

  it('has a pricing link in the hero section', () => {
    render(<Home />)
    const pricingLinks = screen.getAllByRole('link', { name: /pricing/i })
    const heroLink = pricingLinks.find((link) => link.textContent?.includes('View pricing'))
    expect(heroLink).toHaveAttribute('href', '/pricing')
  })

  it('has a pricing link in the CTA section', () => {
    render(<Home />)
    const pricingLinks = screen.getAllByRole('link', { name: /pricing/i })
    const ctaLink = pricingLinks.find((link) => link.textContent?.includes('See plans and pricing'))
    expect(ctaLink).toHaveAttribute('href', '/pricing')
  })

  it('renders iOS App Store download link with correct attributes', () => {
    render(<Home />)
    const appStoreLink = screen.getByRole('link', { name: /app store/i })
    expect(appStoreLink).toHaveAttribute('href', 'https://apps.apple.com/app/warden/id000000')
    expect(appStoreLink).toHaveAttribute('target', '_blank')
    expect(appStoreLink).toHaveAttribute('rel', 'noopener noreferrer')
    expect(appStoreLink).toHaveAttribute('aria-label', 'Download Warden on the App Store')
  })

  it('renders Android Google Play download link with correct attributes', () => {
    render(<Home />)
    const playLink = screen.getByRole('link', { name: /google play/i })
    expect(playLink).toHaveAttribute(
      'href',
      'https://play.google.com/store/apps/details?id=com.warden.app',
    )
    expect(playLink).toHaveAttribute('target', '_blank')
    expect(playLink).toHaveAttribute('rel', 'noopener noreferrer')
    expect(playLink).toHaveAttribute('aria-label', 'Download Warden on Google Play')
  })

  it('has proper heading hierarchy — single h1, h2s for sections', () => {
    const { container } = render(<Home />)
    const h1s = container.querySelectorAll('h1')
    const h2s = container.querySelectorAll('h2')
    const h3s = container.querySelectorAll('h3')
    expect(h1s).toHaveLength(1)
    expect(h2s.length).toBeGreaterThanOrEqual(3)
    expect(h3s.length).toBe(4)
  })

  it('uses semantic section elements', () => {
    const { container } = render(<Home />)
    const sections = container.querySelectorAll('section')
    expect(sections.length).toBeGreaterThanOrEqual(4)
  })

  it('exports metadata with title and description', () => {
    expect(metadata.title).toBe('Warden — Video Review for Coaches')
    expect(metadata.description).toContain('Warden helps EVA After-h coaches')
  })

  it('feature icons have aria-hidden attribute', () => {
    const { container } = render(<Home />)
    const svgs = container.querySelectorAll('section[aria-labelledby="features-heading"] svg')
    svgs.forEach((svg) => {
      expect(svg).toHaveAttribute('aria-hidden', 'true')
    })
  })
})
