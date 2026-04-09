import { describe, it, expect, vi } from 'vitest'
import { NextRequest } from 'next/server'

vi.mock('next/server', async () => {
  const actual = await vi.importActual<typeof import('next/server')>('next/server')
  return {
    ...actual,
    NextResponse: {
      ...actual.NextResponse,
      next: vi.fn(() => ({ type: 'next' })),
      redirect: vi.fn((url: URL) => ({ type: 'redirect', url })),
    },
  }
})

describe('Proxy (Route Protection)', () => {
  it('redirects to sign-in when no session cookie exists', async () => {
    const { proxy } = await import('./proxy')
    const { NextResponse } = await import('next/server')

    const request = new NextRequest('http://localhost:3000/dashboard')

    proxy(request)

    expect(NextResponse.redirect).toHaveBeenCalledWith(
      expect.objectContaining({
        pathname: '/auth/sign-in',
      }),
    )
  })

  it('allows request to proceed when session cookie exists', async () => {
    const { proxy } = await import('./proxy')
    const { NextResponse } = await import('next/server')

    const request = new NextRequest('http://localhost:3000/dashboard', {
      headers: {
        cookie: 'session=valid-session-value',
      },
    })

    proxy(request)

    expect(NextResponse.next).toHaveBeenCalled()
  })

  it('redirects nested dashboard routes without session', async () => {
    const { proxy } = await import('./proxy')
    const { NextResponse } = await import('next/server')

    const request = new NextRequest('http://localhost:3000/dashboard/settings')

    proxy(request)

    expect(NextResponse.redirect).toHaveBeenCalledWith(
      expect.objectContaining({
        pathname: '/auth/sign-in',
      }),
    )
  })

  it('exports config with dashboard matcher', async () => {
    const { config } = await import('./proxy')
    expect(config.matcher).toContain('/dashboard/:path*')
  })
})
