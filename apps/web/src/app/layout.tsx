import type { Metadata } from 'next'
import localFont from 'next/font/local'

import { AuthProvider } from '@/contexts/AuthContext'
import { Header } from '@/components/layout/Header'
import { Footer } from '@/components/layout/Footer'
import { CookieBanner } from '@/components/layout/CookieBanner'

import './globals.css'

const inter = localFont({
  src: [
    {
      path: '../fonts/inter-latin-wght-normal.woff2',
      style: 'normal',
    },
    {
      path: '../fonts/inter-latin-ext-wght-normal.woff2',
      style: 'normal',
    },
  ],
  variable: '--font-sans',
  display: 'swap',
})

export const metadata: Metadata = {
  title: {
    default: 'Warden — Video Review for Coaches',
    template: '%s | Warden',
  },
  description:
    'Warden helps EVA After-h coaches review game sessions, export clips, and analyze minimaps to improve coaching workflows.',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`dark ${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#main-content"
          className="focus:bg-primary focus:text-primary-foreground sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-[6px] focus:px-4 focus:py-2 focus:outline-none"
        >
          Skip to content
        </a>
        <AuthProvider>
          <Header />
          <main id="main-content" className="flex-1">
            {children}
          </main>
          <Footer />
          <CookieBanner />
        </AuthProvider>
      </body>
    </html>
  )
}
