import { useEffect, useState } from 'react'

/** The value, updated only after it has stopped changing for `ms` (e.g. while dragging a slider). */
export function useDebounced<T>(value: T, ms = 250): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return debounced
}
