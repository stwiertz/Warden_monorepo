import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({ name: '[DEFAULT]' })),
  getApps: vi.fn(() => []),
  getApp: vi.fn(() => ({ name: '[DEFAULT]' })),
}))

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  GoogleAuthProvider: vi.fn(),
}))

describe('Firebase Client SDK', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('exports auth and googleProvider', async () => {
    const { auth, googleProvider } = await import('./client')
    expect(auth).toBeDefined()
    expect(googleProvider).toBeDefined()
  })

  it('exports app instance', async () => {
    const { app } = await import('./client')
    expect(app).toBeDefined()
  })

  it('initializes with environment variables config', async () => {
    const { initializeApp } = await import('firebase/app')
    await import('./client')
    expect(initializeApp).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
        projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
      }),
    )
  })
})
