'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { loadAnalytics } from '@/lib/firebase/analytics'

const STORAGE_KEY = 'cookie-consent'

type ConsentState = 'accepted' | 'rejected' | null

export function CookieBanner() {
  const [consent, setConsent] = useState<ConsentState | undefined>(undefined)

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as ConsentState
    setConsent(stored)
    if (stored === 'accepted') {
      loadAnalytics()
    }
  }, [])

  function handleAccept() {
    localStorage.setItem(STORAGE_KEY, 'accepted')
    setConsent('accepted')
    loadAnalytics()
  }

  function handleReject() {
    localStorage.setItem(STORAGE_KEY, 'rejected')
    setConsent('rejected')
  }

  // Don't render during SSR hydration or if consent already given
  if (consent !== null) {
    return null
  }

  return (
    <div
      role="dialog"
      aria-label="Cookie consent"
      className="bg-background border-border/40 fixed inset-x-0 bottom-0 z-50 border-t p-4 shadow-lg sm:p-6"
    >
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 sm:flex-row sm:justify-between">
        <p className="text-muted-foreground text-center text-sm sm:text-left">
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
