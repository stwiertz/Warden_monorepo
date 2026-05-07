# WardenWeb

Web portal for **Warden**, a video review tool for EVA After-h coaches. The portal handles subscription management (bypassing app store fees) and serves as the marketing landing page.

## Tech Stack

- **Next.js 16.2.2** with App Router, TypeScript, `src/` directory
- **React 19.2.4** — Server Components by default
- **Tailwind CSS 4** via `@tailwindcss/postcss`
- **shadcn/ui 4.1.2** (Base UI primitives) — Button, Card, Input, Badge, Alert, Skeleton, Dialog
- **Lucide React** icons
- **Geist** font family (sans + mono)

## Getting Started

```bash
npm install
cp .env.example .env.local   # fill in Firebase + Stripe keys
npm run dev                   # starts at http://localhost:3000
```

## Scripts

| Command                | Description                      |
| ---------------------- | -------------------------------- |
| `npm run dev`          | Start dev server (Turbopack)     |
| `npm run build`        | Production build                 |
| `npm run start`        | Serve production build           |
| `npm run lint`         | Run ESLint                       |
| `npm run format`       | Format all files with Prettier   |
| `npm run format:check` | Check formatting without writing |

## Conventions

- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) enforced by commitlint + husky
- **Formatting**: Prettier (no semicolons, single quotes, trailing commas) enforced by pre-commit hook
- **Imports**: `@/*` alias maps to `./src/*`
- **Components**: PascalCase filenames, placed in `src/components/<feature>/`
- **CSS**: Tailwind utilities only — theme tokens defined in `src/app/globals.css`
