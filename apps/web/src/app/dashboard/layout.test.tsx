import { describe, it, expect, vi, beforeEach } from 'vitest'
import { isValidElement } from 'react'

vi.mock('server-only', () => ({}))

const mockRequireSession = vi.fn()

vi.mock('@/lib/firebase/auth', async () => {
  const actual = await vi.importActual<typeof import('@/lib/firebase/auth')>('@/lib/firebase/auth')
  return {
    ...actual,
    requireSession: (...args: unknown[]) => mockRequireSession(...args),
  }
})

const mockRedirect = vi.fn((path: string) => {
  throw new Error(`REDIRECT:${path}`)
})

vi.mock('next/navigation', () => ({
  redirect: (path: string) => mockRedirect(path),
}))

const mockHeadersGet = vi.fn()

vi.mock('next/headers', () => ({
  headers: vi.fn(async () => ({
    get: mockHeadersGet,
  })),
}))

describe('DashboardLayout (RSC guard)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockHeadersGet.mockReturnValue(null)
  })

  it('renders children when session is valid', async () => {
    const { default: DashboardLayout } = await import('./layout')
    mockRequireSession.mockResolvedValue({ uid: 'abc', email: 'x@y.z' })

    const child = <div>child</div>
    const result = await DashboardLayout({ children: child })

    expect(mockRequireSession).toHaveBeenCalled()
    expect(mockRedirect).not.toHaveBeenCalled()
    expect(isValidElement(result)).toBe(true)
    expect((result as React.ReactElement<{ children: unknown }>).props.children).toBe(child)
  })

  it('redirects to sign-in preserving original pathname from proxy header', async () => {
    const { default: DashboardLayout } = await import('./layout')
    const { UnauthorizedError } = await import('@/lib/firebase/auth')
    mockRequireSession.mockRejectedValue(new UnauthorizedError('SESSION_EXPIRED'))
    mockHeadersGet.mockReturnValue('/dashboard/settings?tab=billing')

    await expect(DashboardLayout({ children: <div>child</div> })).rejects.toThrow(
      /REDIRECT:\/auth\/sign-in\?next=/,
    )
    expect(mockRedirect).toHaveBeenCalledWith(
      '/auth/sign-in?next=' + encodeURIComponent('/dashboard/settings?tab=billing'),
    )
  })

  it('falls back to /dashboard when pathname header is absent', async () => {
    const { default: DashboardLayout } = await import('./layout')
    const { UnauthorizedError } = await import('@/lib/firebase/auth')
    mockRequireSession.mockRejectedValue(new UnauthorizedError('NO_SESSION'))
    mockHeadersGet.mockReturnValue(null)

    await expect(DashboardLayout({ children: <div>child</div> })).rejects.toThrow(
      'REDIRECT:/auth/sign-in?next=%2Fdashboard',
    )
  })

  it('rejects unsafe pathname header via sanitizeRedirect', async () => {
    const { default: DashboardLayout } = await import('./layout')
    const { UnauthorizedError } = await import('@/lib/firebase/auth')
    mockRequireSession.mockRejectedValue(new UnauthorizedError('NO_SESSION'))
    mockHeadersGet.mockReturnValue('//evil.com')

    await expect(DashboardLayout({ children: <div>child</div> })).rejects.toThrow(
      'REDIRECT:/auth/sign-in?next=%2Fdashboard',
    )
  })

  it('rethrows non-auth errors', async () => {
    const { default: DashboardLayout } = await import('./layout')
    mockRequireSession.mockRejectedValue(new Error('db is down'))

    await expect(DashboardLayout({ children: <div>child</div> })).rejects.toThrow('db is down')
    expect(mockRedirect).not.toHaveBeenCalled()
  })
})
