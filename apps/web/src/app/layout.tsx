import type { Metadata } from 'next'
import { Providers } from '@/components/Providers'
import { themeScript } from '@/components/ThemeToggle'
import './globals.css'

export const metadata: Metadata = {
  title: 'GridShift: run compute when the grid is clean',
  description:
    'Find the time and European country with the lowest-carbon electricity for your compute job, using live grid forecasts.',
}

export default function RootLayout({ children }: LayoutProps<'/'>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
