import type { Metadata } from 'next'
import Link from 'next/link'
import { Play, Target, Scissors, Map, ArrowRight, Smartphone } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Warden — Video Review for Coaches',
  description:
    'Warden helps EVA After-h coaches review game sessions, export clips, and analyze minimaps to improve coaching workflows.',
  openGraph: {
    title: 'Warden — Video Review for Coaches',
    description:
      'Warden helps EVA After-h coaches review game sessions, export clips, and analyze minimaps to improve coaching workflows.',
    type: 'website',
    locale: 'en_US',
    siteName: 'Warden',
  },
}

const ctaClasses =
  'bg-primary text-primary-foreground hover:bg-primary/80 focus-visible:border-ring focus-visible:ring-ring/50 inline-flex h-9 items-center justify-center gap-1.5 rounded-lg px-6 text-base font-medium transition-colors focus-visible:ring-3'

const features = [
  {
    icon: Play,
    title: 'Session Review',
    description:
      'Review full game sessions with frame-by-frame precision and annotate key moments.',
  },
  {
    icon: Scissors,
    title: 'Clip Export',
    description: 'Export and share highlights with your team to reinforce learning and strategy.',
  },
  {
    icon: Map,
    title: 'Minimap Analysis',
    description:
      'Visualize positioning and rotations on the minimap to identify strategic patterns.',
  },
  {
    icon: Target,
    title: 'Coaching Workflows',
    description: 'Streamline your review process with tools designed for coaching efficiency.',
  },
]

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      {/* Hero Section */}
      <section className="flex flex-col items-center gap-6 px-4 py-16 text-center sm:px-6 md:py-24 lg:py-32">
        <h1 className="text-foreground max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl lg:text-6xl">
          Better coaching starts with better review
        </h1>
        <p className="text-muted-foreground max-w-xl text-base leading-relaxed sm:text-lg md:text-xl">
          Warden gives EVA After-h coaches the tools to review sessions, export clips, and analyze
          minimap data — so you can focus on improving your team.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Link href="/pricing" className={ctaClasses}>
            View pricing
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </section>

      {/* Features Section */}
      <section
        aria-labelledby="features-heading"
        className="bg-muted/50 px-4 py-16 sm:px-6 md:py-24"
      >
        <div className="mx-auto max-w-5xl">
          <h2
            id="features-heading"
            className="text-foreground mb-12 text-center text-2xl font-bold tracking-tight sm:text-3xl"
          >
            Everything you need to coach effectively
          </h2>
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((feature) => (
              <div key={feature.title} className="flex flex-col items-center gap-3 text-center">
                <div className="bg-primary/10 flex size-12 items-center justify-center rounded-lg">
                  <feature.icon className="text-primary size-6" aria-hidden="true" />
                </div>
                <h3 className="text-foreground text-lg font-semibold">{feature.title}</h3>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing CTA Section */}
      <section className="flex flex-col items-center gap-6 px-4 py-16 text-center sm:px-6 md:py-24">
        <h2 className="text-foreground text-2xl font-bold tracking-tight sm:text-3xl">
          Start coaching smarter today
        </h2>
        <p className="text-muted-foreground max-w-md">
          Plans start at EUR 7.99/month. Save over 15% with a yearly subscription.
        </p>
        <Link href="/pricing" className={ctaClasses}>
          See plans and pricing
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </section>

      {/* Download Section */}
      <section
        aria-labelledby="download-heading"
        className="bg-muted/50 px-4 py-16 text-center sm:px-6 md:py-24"
      >
        <div className="mx-auto flex max-w-xl flex-col items-center gap-6">
          <div className="bg-primary/10 flex size-12 items-center justify-center rounded-lg">
            <Smartphone className="text-primary size-6" aria-hidden="true" />
          </div>
          <h2
            id="download-heading"
            className="text-foreground text-2xl font-bold tracking-tight sm:text-3xl"
          >
            Get the Warden app
          </h2>
          <p className="text-muted-foreground">
            Download Warden on your phone to review sessions on the go.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <a
              href="https://apps.apple.com/app/warden/id000000"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Download Warden on the App Store"
              className="border-border bg-background text-foreground hover:bg-muted focus-visible:border-ring focus-visible:ring-ring/50 inline-flex h-12 items-center justify-center gap-2 rounded-lg border px-5 text-sm font-medium transition-colors focus-visible:ring-3"
            >
              <svg className="size-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z" />
              </svg>
              App Store
            </a>
            <a
              href="https://play.google.com/store/apps/details?id=com.warden.app"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Download Warden on Google Play"
              className="border-border bg-background text-foreground hover:bg-muted focus-visible:border-ring focus-visible:ring-ring/50 inline-flex h-12 items-center justify-center gap-2 rounded-lg border px-5 text-sm font-medium transition-colors focus-visible:ring-3"
            >
              <svg className="size-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M3.61 1.02 14.52 12 3.61 22.98A1.07 1.07 0 0 1 3 22.06V1.94c0-.38.23-.73.61-.92zM15.4 12.88l-2.54 2.54-9.27 5.35 8.97-8.97 2.84 1.08zM20.16 10.81c.58.34.84.82.84 1.19 0 .37-.26.85-.84 1.19l-3.15 1.82-2.79-2.79 2.79-2.79 3.15 1.38zM3.59 1.68l9.27 5.35 2.54 2.54-2.84 1.08-8.97-8.97z" />
              </svg>
              Google Play
            </a>
          </div>
        </div>
      </section>
    </main>
  )
}
