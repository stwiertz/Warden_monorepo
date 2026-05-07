import 'server-only'

import { cookies } from 'next/headers'

import { adminAuth } from '@/lib/firebase/admin'

const SESSION_COOKIE_NAME = 'session'

export type UnauthorizedCode = 'NO_SESSION' | 'SESSION_EXPIRED' | 'SESSION_REVOKED' | 'UNAUTHORIZED'

export class UnauthorizedError extends Error {
  readonly code: UnauthorizedCode

  constructor(code: UnauthorizedCode, message = 'Authentication required', options?: ErrorOptions) {
    super(message, options)
    this.code = code
    this.name = 'UnauthorizedError'
  }
}

export interface Session {
  uid: string
  email: string | undefined
}

export async function requireSession(): Promise<Session> {
  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME)?.value

  if (!sessionCookie) {
    throw new UnauthorizedError('NO_SESSION')
  }

  try {
    const decoded = await adminAuth.verifySessionCookie(sessionCookie, true)
    return { uid: decoded.uid, email: decoded.email }
  } catch (err) {
    const code = (err as { code?: string } | null)?.code
    if (code === 'auth/session-cookie-revoked') {
      throw new UnauthorizedError('SESSION_REVOKED', 'Authentication required', { cause: err })
    }
    if (code === 'auth/session-cookie-expired' || code === 'auth/id-token-expired') {
      throw new UnauthorizedError('SESSION_EXPIRED', 'Authentication required', { cause: err })
    }
    throw new UnauthorizedError('UNAUTHORIZED', 'Authentication required', { cause: err })
  }
}

export async function getSession(): Promise<Session | null> {
  try {
    return await requireSession()
  } catch (err) {
    if (err instanceof UnauthorizedError) return null
    throw err
  }
}

export function unauthorizedResponse(error: UnauthorizedError): Response {
  return Response.json(
    { error: { code: error.code, message: 'Authentication required' } },
    { status: 401 },
  )
}

export async function withAuth<T>(
  handler: (session: Session) => Promise<T>,
): Promise<T | Response> {
  try {
    const session = await requireSession()
    return await handler(session)
  } catch (err) {
    if (err instanceof UnauthorizedError) return unauthorizedResponse(err)
    throw err
  }
}
