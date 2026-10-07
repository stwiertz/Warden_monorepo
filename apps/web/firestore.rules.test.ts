/**
 * Story 1.14 — Firestore security-rules matrix (AC2), run against the local emulator.
 *
 * Run: `pnpm --filter web test:rules` (see firestore.rules.test.md). Not part of `pnpm test`.
 * Project id `demo-warden-rules`: the `demo-` prefix keeps the emulator fully offline from
 * real Firebase projects and credentials.
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment,
} from '@firebase/rules-unit-testing'
import {
  collection,
  collectionGroup,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  setDoc,
  updateDoc,
  type Firestore,
} from 'firebase/firestore'
import { afterAll, beforeAll, beforeEach, describe, it } from 'vitest'

const PROJECT_ID = 'demo-warden-rules'
const OWNER = 'u1'

let testEnv: RulesTestEnvironment

beforeAll(async () => {
  // FIRESTORE_EMULATOR_HOST is provided by `firebase emulators:exec`; no host/port hard-coded.
  testEnv = await initializeTestEnvironment({
    projectId: PROJECT_ID,
    firestore: {
      rules: readFileSync(path.resolve(__dirname, 'firestore.rules'), 'utf8'),
    },
  })
})

beforeEach(async () => {
  await testEnv.clearFirestore()
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore()
    await setDoc(doc(db, 'users/u1'), { subscriptionStatus: 'active' })
    await setDoc(doc(db, 'users/u2'), { subscriptionStatus: 'active' })
    await setDoc(doc(db, 'users/u1/anything/x'), { note: 'sub-collection' })
    // Envelope-shaped, as written by Story 1.13's operator flow (rules never validate data).
    await setDoc(doc(db, 'detection_config/latest'), {
      envelope_version: 1,
      revision: 1,
      configs: {},
    })
    await setDoc(doc(db, 'detection_config/other'), {
      envelope_version: 1,
      revision: 0,
      configs: {},
    })
    await setDoc(doc(db, 'detection_config/latest/history/r0'), { revision: 0 })
    await setDoc(doc(db, 'stripe_events/evt_1'), { type: 'checkout.session.completed' })
    await setDoc(doc(db, 'random/doc'), { any: true })
  })
})

afterAll(async () => {
  await testEnv?.cleanup()
})

type Who = 'anon' | 'u1'
const WHO: Who[] = ['anon', 'u1']

function db(who: Who): Firestore {
  return (who === 'anon'
    ? testEnv.unauthenticatedContext()
    : testEnv.authenticatedContext(OWNER)
  ).firestore() as unknown as Firestore
}

/** Asserts every client write verb (create, set-overwrite, update, delete) is denied. */
async function assertAllWritesFail(fs: Firestore, docPath: string) {
  const parent = docPath.split('/').slice(0, -1).join('/')
  await assertFails(setDoc(doc(fs, `${parent}/brand-new-doc`), { x: 1 })) // create
  await assertFails(setDoc(doc(fs, docPath), { x: 1 })) // overwrite (update of existing)
  await assertFails(updateDoc(doc(fs, docPath), { x: 2 })) // update
  await assertFails(deleteDoc(doc(fs, docPath))) // delete
}

describe('users/{userId}', () => {
  it('users/u1 get: anon deny, owner allow', async () => {
    await assertFails(getDoc(doc(db('anon'), 'users/u1')))
    await assertSucceeds(getDoc(doc(db('u1'), 'users/u1')))
  })

  it.each(WHO)('users/u2 get: %s deny (not your doc)', async (who) => {
    await assertFails(getDoc(doc(db(who), 'users/u2')))
  })

  it.each(WHO)('users list (unfiltered): %s deny', async (who) => {
    await assertFails(getDocs(collection(db(who), 'users')))
  })

  it.each(WHO)('users/u1 create/set/update/delete: %s deny [INVARIANT 2]', async (who) => {
    await assertAllWritesFail(db(who), 'users/u1')
  })

  it.each(WHO)('users/u1/anything/x get: %s deny (sub-collection -> catch-all)', async (who) => {
    await assertFails(getDoc(doc(db(who), 'users/u1/anything/x')))
  })

  it('users/u3 create by u3 itself (first sign-in): deny [INVARIANT 2]', async () => {
    const u3 = testEnv.authenticatedContext('u3').firestore() as unknown as Firestore
    await assertFails(setDoc(doc(u3, 'users/u3'), { subscriptionStatus: 'active' }))
  })
})

describe('detection_config/{docId}', () => {
  it('detection_config/latest get: anon deny, signed-in allow (the Story 1.13 read)', async () => {
    await assertFails(getDoc(doc(db('anon'), 'detection_config/latest')))
    await assertSucceeds(getDoc(doc(db('u1'), 'detection_config/latest')))
  })

  it('detection_config/other get: anon deny, signed-in allow ({docId}, D1)', async () => {
    await assertFails(getDoc(doc(db('anon'), 'detection_config/other')))
    await assertSucceeds(getDoc(doc(db('u1'), 'detection_config/other')))
  })

  it('detection_config list: anon deny, signed-in allow (read = get + list)', async () => {
    await assertFails(getDocs(collection(db('anon'), 'detection_config')))
    await assertSucceeds(getDocs(collection(db('u1'), 'detection_config')))
  })

  it.each(WHO)(
    'detection_config/latest/history/r0 get: %s deny (sub-collection -> catch-all)',
    async (who) => {
      await assertFails(getDoc(doc(db(who), 'detection_config/latest/history/r0')))
    },
  )

  it.each(WHO)('detection_config/latest create/update/delete: %s deny', async (who) => {
    await assertAllWritesFail(db(who), 'detection_config/latest')
  })
})

describe('stripe_events/{eventId}', () => {
  it.each(WHO)('stripe_events/evt_1 get/list/set: %s deny', async (who) => {
    const fs = db(who)
    await assertFails(getDoc(doc(fs, 'stripe_events/evt_1')))
    await assertFails(getDocs(collection(fs, 'stripe_events')))
    await assertFails(setDoc(doc(fs, 'stripe_events/evt_1'), { x: 1 }))
  })
})

describe('collection-group queries', () => {
  it.each(WHO)(
    'collectionGroup users / anything / history / stripe_events: %s deny',
    async (who) => {
      const fs = db(who)
      for (const group of ['users', 'anything', 'history', 'stripe_events']) {
        await assertFails(getDocs(collectionGroup(fs, group)))
      }
    },
  )
})

describe('catch-all', () => {
  it.each(WHO)('random/doc get/set: %s deny', async (who) => {
    const fs = db(who)
    await assertFails(getDoc(doc(fs, 'random/doc')))
    await assertFails(setDoc(doc(fs, 'random/doc'), { x: 1 }))
  })
})
