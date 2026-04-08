import 'server-only'

import { initializeApp, getApps, cert } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { getFirestore } from 'firebase-admin/firestore'

const apps = getApps()

const app =
  apps.length > 0
    ? apps[0]
    : initializeApp({
        credential: cert(JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_KEY!)),
      })

export const adminAuth = getAuth(app)
export const adminDb = getFirestore(app)
