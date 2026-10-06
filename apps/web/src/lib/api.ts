import { createGridshiftClient } from '@gridshift/api-client'

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
)

export const api = createGridshiftClient(API_URL)
