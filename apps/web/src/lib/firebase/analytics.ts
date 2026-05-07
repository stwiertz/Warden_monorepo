let analyticsLoaded = false

export async function loadAnalytics(): Promise<void> {
  if (analyticsLoaded) return
  if (typeof window === 'undefined') return

  try {
    const { app } = await import('@/lib/firebase/client')
    const { getAnalytics, isSupported } = await import('firebase/analytics')
    const supported = await isSupported()
    if (supported) {
      getAnalytics(app)
      analyticsLoaded = true
    }
  } catch {
    // Firebase Analytics not available — silently skip
  }
}
