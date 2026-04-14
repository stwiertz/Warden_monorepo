import { signOut, type User } from 'firebase/auth'

import { auth } from '@/lib/firebase/client'

export async function createSessionAndRedirect(
  user: User,
  redirect: (path: string) => void,
): Promise<void> {
  const idToken = await user.getIdToken()

  const response = await fetch('/api/auth/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idToken }),
  })

  if (!response.ok) {
    throw new Error('Failed to create session')
  }

  redirect('/dashboard')
}

export async function destroySessionAndRedirect(redirect: (path: string) => void): Promise<void> {
  let signOutError: unknown = null
  try {
    await signOut(auth)
  } catch (error) {
    signOutError = error
  }

  const response = await fetch('/api/auth/session', { method: 'DELETE' })

  if (signOutError) throw signOutError
  if (!response.ok) {
    throw new Error('Failed to destroy session')
  }

  redirect('/')
}
