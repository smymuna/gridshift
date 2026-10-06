import { Suspense } from 'react'
import { Planner } from '@/components/Planner'
import { ThemeToggle } from '@/components/ThemeToggle'
import { API_URL } from '@/lib/api'

const REPO = 'https://github.com/smymuna/gridshift'

const steps = [
  {
    title: 'Live grid data',
    text: 'Measured and forecast carbon intensity for 26 European countries from Energy-Charts (Fraunhofer ISE), refreshed every 15 minutes.',
  },
  {
    title: 'Window search',
    text: 'For every possible start time and country, the API computes the time-weighted average intensity of your job and picks the lowest that meets the deadline.',
  },
  {
    title: 'Compared with now',
    text: 'The result is compared with starting immediately in your current location, so you see exactly what waiting or moving saves.',
  },
]

export default function Home() {
  return (
    <>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
          <a href="/" className="flex items-center gap-2 font-semibold">
            <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true">
              <rect width="32" height="32" rx="7" fill="var(--accent)" />
              <path d="M18 5 9 18h6l-2 9 10-14h-6z" fill="var(--accent-ink)" />
            </svg>
            GridShift
          </a>
          <nav className="flex items-center gap-4 text-sm text-ink-2">
            <a href={`${API_URL}/docs`} className="hover:text-ink">
              API
            </a>
            <a href={REPO} className="hover:text-ink">
              GitHub
            </a>
            <ThemeToggle />
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pb-16">
        <section className="py-8 sm:py-10">
          <h1 className="max-w-3xl text-3xl leading-tight font-semibold tracking-tight sm:text-4xl">
            Run your compute when and where the grid is cleanest
          </h1>
          <p className="mt-3 max-w-2xl text-ink-2">
            Electricity in Europe can be ten times cleaner in one hour or country than another. Tell
            GridShift how long your job runs and when it must finish; it finds the lowest-carbon
            time and place to run it.
          </p>
        </section>

        <Suspense fallback={<div className="skeleton h-[520px]" />}>
          <Planner />
        </Suspense>

        <section className="mt-14">
          <h2 className="text-lg font-semibold">How it works</h2>
          <ol className="mt-4 grid gap-4 sm:grid-cols-3">
            {steps.map((s, i) => (
              <li key={s.title} className="rounded-2xl border border-line bg-surface p-5">
                <span className="tabular text-sm font-semibold text-accent">{i + 1}</span>
                <h3 className="mt-1 font-semibold">{s.title}</h3>
                <p className="mt-1 text-sm text-ink-2">{s.text}</p>
              </li>
            ))}
          </ol>
          <p className="mt-4 text-sm text-ink-2">
            Read the design decisions in the{' '}
            <a className="text-accent underline" href={`${REPO}/tree/main/docs/adr`}>
              architecture decision records
            </a>
            .
          </p>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto max-w-6xl px-4 py-6 text-sm text-muted">
          Carbon intensity data: Energy-Charts.info, Fraunhofer ISE. Average (location-based)
          intensity; forecasts can be wrong. Built by{' '}
          <a className="underline" href="https://smymuna.github.io">
            Mymuna Sultana
          </a>
          .
        </div>
      </footer>
    </>
  )
}
