import { NextResponse } from 'next/server'

import type { NextRequest } from 'next/server'

const SESSION_COOKIE_NAME = 'session'

export function proxy(request: NextRequest) {
  const session = request.cookies.get(SESSION_COOKIE_NAME)

  if (!session) {
    return NextResponse.redirect(new URL('/auth/sign-in', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*'],
}
