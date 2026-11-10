import { headers } from 'next/headers'
import { redirect } from 'next/navigation'

import { requireSession, UnauthorizedError } from '@/lib/firebase/auth'
import { sanitizeRedirect } from '@/lib/utils'
import { PATHNAME_HEADER } from '@/proxy'

import type { Metadata } from 'next'
import type { ReactNode } from 'react'

export const metadata: Metadata = {
  title: 'Dashboard',
  // UX §3.3.1: protected user data, no OG preview surface. `null` stops the root card from being
  // inherited (shallow merge).
  robots: { index: false, follow: false },
  openGraph: null,
  twitter: null,
}

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  try {
    await requireSession()
  } catch (err) {
    if (err instanceof UnauthorizedError) {
      const hdrs = await headers()
      const originalPath = sanitizeRedirect(hdrs.get(PATHNAME_HEADER))
      const signInUrl = `/auth/sign-in?next=${encodeURIComponent(originalPath)}`
      redirect(signInUrl)
    }
    throw err
  }

  return <>{children}</>
}
