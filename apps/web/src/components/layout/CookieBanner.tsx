'use client'

import { useSyncExternalStore, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { loadAnalytics } from '@/lib/firebase/analytics'

const STORAGE_KEY = 'cookie-consent'

type ConsentState = 'accepted' | 'rejected' | null
type StoreSnapshot = ConsentState | 'unknown'

const listeners = new Set<() => void>()

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange)
  return () => {
    listeners.delete(onChange)
  }
}

function emit() {
  listeners.forEach((l) => l())
}

function getSnapshot(): StoreSnapshot {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'accepted' || stored === 'rejected' ? stored : null
}

function getServerSnapshot(): StoreSnapshot {
  return 'unknown'
}

export function CookieBanner() {
  const consent = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)

  useEffect(() => {
    if (consent === 'accepted') {
      loadAnalytics()
    }
  }, [consent])

  function handleAccept() {
    localStorage.setItem(STORAGE_KEY, 'accepted')
    emit()
  }

  function handleReject() {
    localStorage.setItem(STORAGE_KEY, 'rejected')
    emit()
  }

  if (consent !== null) {
    return null
  }

  return (
    <div
      role="dialog"
      aria-label="Cookie consent"
      aria-describedby="cookie-consent-description"
      className="bg-background border-border/40 fixed inset-x-0 bottom-0 z-50 border-t p-4 shadow-lg sm:p-6"
    >
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 sm:flex-row sm:justify-between">
        <p
          id="cookie-consent-description"
          className="text-muted-foreground text-center text-sm sm:text-left"
        >
          We use analytics cookies to understand how you use our site and improve your experience.
        </p>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" size="sm" onClick={handleReject}>
            Reject
          </Button>
          <Button size="sm" onClick={handleAccept}>
            Accept
          </Button>
        </div>
      </div>
    </div>
  )
}
