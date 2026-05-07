import Link from 'next/link'

import { HeaderAuthActions } from './HeaderAuthActions'

export function Header() {
  return (
    <header className="border-border/40 bg-background/95 supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50 border-b backdrop-blur">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6">
        <Link
          href="/"
          className="text-foreground focus-visible:ring-ring/50 rounded-sm text-lg font-bold tracking-tight outline-none focus-visible:ring-3"
        >
          Warden
        </Link>
        <nav aria-label="Main navigation">
          <ul className="flex items-center gap-1">
            <HeaderAuthActions />
          </ul>
        </nav>
      </div>
    </header>
  )
}
