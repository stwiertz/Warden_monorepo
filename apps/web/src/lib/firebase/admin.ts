import 'server-only'

import { initializeApp, getApps, cert } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { getFirestore } from 'firebase-admin/firestore'

import type { App } from 'firebase-admin/app'

let _app: App | undefined

function getApp() {
  if (_app) return _app
  const apps = getApps()
  if (apps.length > 0) {
    _app = apps[0]
  } else {
    const serviceAccountKey = process.env.FIREBASE_SERVICE_ACCOUNT_KEY
    if (!serviceAccountKey) {
      throw new Error(
        'FIREBASE_SERVICE_ACCOUNT_KEY environment variable is not set. ' +
          'Set it to a JSON string of your Firebase service account credentials.',
      )
    }
    _app = initializeApp({
      credential: cert(JSON.parse(serviceAccountKey)),
    })
  }
  return _app
}

export const adminAuth = new Proxy({} as ReturnType<typeof getAuth>, {
  get(_, prop) {
    const target = getAuth(getApp())
    const value = (target as unknown as Record<string | symbol, unknown>)[prop]
    return typeof value === 'function' ? value.bind(target) : value
  },
})

export const adminDb = new Proxy({} as ReturnType<typeof getFirestore>, {
  get(_, prop) {
    const target = getFirestore(getApp())
    const value = (target as unknown as Record<string | symbol, unknown>)[prop]
    return typeof value === 'function' ? value.bind(target) : value
  },
})
