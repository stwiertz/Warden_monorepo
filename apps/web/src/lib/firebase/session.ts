import type { User } from 'firebase/auth'

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
