import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { CookieBanner } from './CookieBanner'

vi.mock('@/lib/firebase/analytics', () => ({
  loadAnalytics: vi.fn(),
}))

const mockLocalStorage = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    clear: () => {
      store = {}
    },
  }
})()

Object.defineProperty(window, 'localStorage', { value: mockLocalStorage })

describe('CookieBanner', () => {
  beforeEach(() => {
    mockLocalStorage.clear()
    mockLocalStorage.getItem.mockClear()
    mockLocalStorage.setItem.mockClear()
    vi.clearAllMocks()
  })

  it('shows the banner when no consent preference exists', () => {
    render(<CookieBanner />)
    expect(screen.getByRole('dialog', { name: /cookie consent/i })).toBeInTheDocument()
  })

  it('shows Accept and Reject buttons', () => {
    render(<CookieBanner />)
    expect(screen.getByRole('button', { name: /accept/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
  })

  it('hides the banner when Accept is clicked', () => {
    render(<CookieBanner />)
    fireEvent.click(screen.getByRole('button', { name: /accept/i }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('saves "accepted" to localStorage on Accept', () => {
    render(<CookieBanner />)
    fireEvent.click(screen.getByRole('button', { name: /accept/i }))
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookie-consent', 'accepted')
  })

  it('hides the banner when Reject is clicked', () => {
    render(<CookieBanner />)
    fireEvent.click(screen.getByRole('button', { name: /reject/i }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('saves "rejected" to localStorage on Reject', () => {
    render(<CookieBanner />)
    fireEvent.click(screen.getByRole('button', { name: /reject/i }))
    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('cookie-consent', 'rejected')
  })

  it('calls loadAnalytics on Accept', async () => {
    const { loadAnalytics } = await import('@/lib/firebase/analytics')
    render(<CookieBanner />)
    fireEvent.click(screen.getByRole('button', { name: /accept/i }))
    expect(loadAnalytics).toHaveBeenCalled()
  })

  it('does not call loadAnalytics on Reject', async () => {
    const { loadAnalytics } = await import('@/lib/firebase/analytics')
    render(<CookieBanner />)
    fireEvent.click(screen.getByRole('button', { name: /reject/i }))
    expect(loadAnalytics).not.toHaveBeenCalledAfter?.(mockLocalStorage.setItem)
  })

  it('does not show banner if consent was previously accepted', () => {
    mockLocalStorage.getItem.mockReturnValue('accepted')
    render(<CookieBanner />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('does not show banner if consent was previously rejected', () => {
    mockLocalStorage.getItem.mockReturnValue('rejected')
    render(<CookieBanner />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
