import { NextResponse } from 'next/server'

import type { NextRequest } from 'next/server'

const SESSION_COOKIE_NAME = 'session'
export const PATHNAME_HEADER = 'x-warden-pathname'

export function proxy(request: NextRequest) {
  const session = request.cookies.get(SESSION_COOKIE_NAME)
  const fullPath = request.nextUrl.pathname + request.nextUrl.search

  if (!session) {
    const signInUrl = new URL('/auth/sign-in', request.url)
    signInUrl.searchParams.set('next', fullPath)
    return NextResponse.redirect(signInUrl)
  }

  const forwardedHeaders = new Headers(request.headers)
  forwardedHeaders.set(PATHNAME_HEADER, fullPath)
  return NextResponse.next({ request: { headers: forwardedHeaders } })
}

export const config = {
  matcher: ['/dashboard/:path*'],
}
