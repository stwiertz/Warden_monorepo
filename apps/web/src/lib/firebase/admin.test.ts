import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('server-only', () => ({}))

vi.mock('firebase-admin/app', () => ({
  initializeApp: vi.fn(() => ({ name: '[DEFAULT]' })),
  getApps: vi.fn(() => []),
  cert: vi.fn((config) => config),
}))

vi.mock('firebase-admin/auth', () => ({
  getAuth: vi.fn(() => ({
    verifyIdToken: vi.fn(),
    createSessionCookie: vi.fn(),
    verifySessionCookie: vi.fn(),
  })),
}))

vi.mock('firebase-admin/firestore', () => ({
  getFirestore: vi.fn(() => ({ collection: vi.fn() })),
}))

describe('Firebase Admin SDK', () => {
  beforeEach(() => {
    process.env.FIREBASE_SERVICE_ACCOUNT_KEY = JSON.stringify({
      type: 'service_account',
      project_id: 'test-project',
    })
    vi.resetModules()
  })

  it('exports adminAuth', async () => {
    const { adminAuth } = await import('./admin')
    expect(adminAuth).toBeDefined()
    expect(adminAuth.verifyIdToken).toBeDefined()
  })

  it('exports adminDb', async () => {
    const { adminDb } = await import('./admin')
    expect(adminDb).toBeDefined()
  })

  it('initializes with service account credentials', async () => {
    const { initializeApp, cert } = await import('firebase-admin/app')
    await import('./admin')
    expect(cert).toHaveBeenCalledWith({
      type: 'service_account',
      project_id: 'test-project',
    })
    expect(initializeApp).toHaveBeenCalled()
  })

  it('uses singleton pattern — does not re-initialize if app exists', async () => {
    const { getApps, initializeApp } = await import('firebase-admin/app')
    vi.mocked(getApps).mockReturnValue([{ name: '[DEFAULT]' } as never])
    vi.mocked(initializeApp).mockClear()
    await import('./admin')
    expect(initializeApp).not.toHaveBeenCalled()
  })
})
