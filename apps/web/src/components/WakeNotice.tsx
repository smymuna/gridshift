'use client'

import { useEffect, useState } from 'react'

interface Props {
  waiting: boolean
  afterMs?: number
}

/** The hosted API sleeps after 15 idle minutes (Render's free plan), and the first request
 *  then takes up to a minute. Say so instead of leaving a skeleton that looks broken. */
export function WakeNotice({ waiting, afterMs = 4000 }: Props) {
  const [slow, setSlow] = useState(false)

  useEffect(() => {
    if (!waiting) {
      setSlow(false)
      return
    }
    const id = window.setTimeout(() => setSlow(true), afterMs)
    return () => window.clearTimeout(id)
  }, [waiting, afterMs])

  if (!waiting || !slow) return null
  return (
    <p role="status" className="rounded-2xl border border-line bg-surface p-4 text-sm text-ink-2">
      <span className="font-semibold text-ink">Waking up the server…</span> GridShift&apos;s API
      runs on a free host that sleeps when nobody is using it. The first request can take up to a
      minute; after that it&apos;s fast.
    </p>
  )
}
