import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { Header } from './Header'

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ user: null, loading: false, error: null }),
}))

describe('Header', () => {
  it('renders a header element', () => {
    render(<Header />)
    expect(screen.getByRole('banner')).toBeInTheDocument()
  })

  it('renders a nav with "Main navigation" label', () => {
    render(<Header />)
    expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument()
  })

  it('renders the Warden brand link pointing to home', () => {
    render(<Header />)
    const brandLink = screen.getByRole('link', { name: /warden/i })
    expect(brandLink).toHaveAttribute('href', '/')
  })

  it('renders Home navigation link', () => {
    render(<Header />)
    const homeLink = screen.getByRole('link', { name: /^home$/i })
    expect(homeLink).toHaveAttribute('href', '/')
  })

  it('renders Pricing navigation link', () => {
    render(<Header />)
    const pricingLink = screen.getByRole('link', { name: /^pricing$/i })
    expect(pricingLink).toHaveAttribute('href', '/pricing')
  })

  it('uses semantic header and nav elements', () => {
    const { container } = render(<Header />)
    expect(container.querySelector('header')).toBeInTheDocument()
    expect(container.querySelector('nav')).toBeInTheDocument()
  })

  it('navigation links have focus-visible ring classes', () => {
    render(<Header />)
    const homeLink = screen.getByRole('link', { name: /^home$/i })
    expect(homeLink.className).toContain('focus-visible:ring')
  })

  it('renders the auth-actions slot inside the nav (Sign in link when anonymous)', () => {
    render(<Header />)
    const nav = screen.getByRole('navigation', { name: /main navigation/i })
    const signInLink = screen.getByRole('link', { name: /^sign in$/i })
    expect(signInLink).toHaveAttribute('href', '/auth/sign-in')
    expect(nav.contains(signInLink)).toBe(true)
  })
})
