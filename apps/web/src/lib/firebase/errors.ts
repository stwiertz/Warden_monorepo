const SHARED_ERROR_MESSAGES: Record<string, string> = {
  'auth/too-many-requests': 'Too many attempts. Please wait and try again.',
  'auth/network-request-failed': 'Network error. Please try again.',
}

const SIGN_IN_ERROR_MESSAGES: Record<string, string> = {
  ...SHARED_ERROR_MESSAGES,
  'auth/invalid-credential': 'Invalid email or password.',
  'auth/user-disabled': 'This account has been disabled.',
  'auth/popup-closed-by-user': 'Sign-in was cancelled.',
  'auth/cancelled-popup-request': 'Sign-in was cancelled.',
}

const REGISTRATION_ERROR_MESSAGES: Record<string, string> = {
  ...SHARED_ERROR_MESSAGES,
  'auth/email-already-in-use': 'An account with this email already exists. Try signing in instead.',
  'auth/weak-password': 'Password is too weak. Use at least 8 characters.',
  'auth/invalid-email': 'Please enter a valid email address.',
}

function getFirebaseErrorCode(error: unknown): string | null {
  if (error instanceof Error && 'code' in error) {
    return (error as { code: string }).code
  }
  return null
}

export function getSignInErrorMessage(error: unknown): string {
  const code = getFirebaseErrorCode(error)
  if (code)
    return SIGN_IN_ERROR_MESSAGES[code] ?? 'An error occurred during sign-in. Please try again.'
  return 'An error occurred during sign-in. Please try again.'
}

export function getRegistrationErrorMessage(error: unknown): string {
  const code = getFirebaseErrorCode(error)
  if (code)
    return (
      REGISTRATION_ERROR_MESSAGES[code] ??
      'An error occurred during registration. Please try again.'
    )
  return 'An error occurred during registration. Please try again.'
}
