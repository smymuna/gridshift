'use client'

export function ThemeToggle() {
  const toggle = () => {
    const root = document.documentElement
    const dark = root.dataset.theme
      ? root.dataset.theme === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches
    root.dataset.theme = dark ? 'light' : 'dark'
    try {
      localStorage.setItem('theme', root.dataset.theme)
    } catch {
      // storage blocked: the toggle still works for this visit
    }
  }
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle dark mode"
      className="grid h-9 w-9 place-items-center rounded-lg border border-line text-ink-2 hover:bg-surface"
    >
      ◐
    </button>
  )
}

/** Runs before paint so a saved theme never flashes the wrong colours. */
export const themeScript = `try{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}`
