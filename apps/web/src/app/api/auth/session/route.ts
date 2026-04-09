import { cookies } from 'next/headers'
import { z } from 'zod/v4'

import { adminAuth } from '@/lib/firebase/admin'

const SESSION_COOKIE_NAME = 'session'
const SESSION_EXPIRY_DAYS = 7
const SESSION_EXPIRY_MS = SESSION_EXPIRY_DAYS * 24 * 60 * 60 * 1000

const idTokenSchema = z.object({
  idToken: z.string().min(1),
})

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const parsed = idTokenSchema.safeParse(body)

    if (!parsed.success) {
      return Response.json(
        { error: { code: 'INVALID_REQUEST', message: 'Missing or invalid idToken' } },
        { status: 400 },
      )
    }

    const { idToken } = parsed.data

    await adminAuth.verifyIdToken(idToken)

    const sessionCookie = await adminAuth.createSessionCookie(idToken, {
      expiresIn: SESSION_EXPIRY_MS,
    })

    const cookieStore = await cookies()
    cookieStore.set(SESSION_COOKIE_NAME, sessionCookie, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: SESSION_EXPIRY_DAYS * 24 * 60 * 60,
    })

    return Response.json({ data: { status: 'success' } })
  } catch {
    return Response.json(
      { error: { code: 'INVALID_TOKEN', message: 'Failed to verify ID token' } },
      { status: 401 },
    )
  }
}

export async function DELETE() {
  const cookieStore = await cookies()
  cookieStore.delete(SESSION_COOKIE_NAME)

  return Response.json({ data: { status: 'success' } })
}
