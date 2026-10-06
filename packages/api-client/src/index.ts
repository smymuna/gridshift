import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type { paths } from './schema'

type Schemas = components['schemas']
export type Zone = Schemas['ZoneOut']
export type IntensityResponse = Schemas['IntensityResponse']
export type IntensityPoint = Schemas['PointOut']
export type ScheduleRequest = Schemas['ScheduleRequest']
export type ScheduleResponse = Schemas['ScheduleResponse']
export type Window = Schemas['WindowOut']

/** RFC 9457 problem details, as returned by every API error. */
export interface Problem {
  type?: string
  title: string
  status: number
  detail?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly title: string

  constructor(problem: Problem) {
    super(problem.detail ?? problem.title)
    this.name = 'ApiError'
    this.status = problem.status
    this.title = problem.title
  }
}

function toApiError(error: unknown, status: number): ApiError {
  if (error && typeof error === 'object' && 'title' in error) {
    return new ApiError(error as Problem)
  }
  // FastAPI request validation errors ({"detail": [...]}) and anything unexpected
  const detail =
    error && typeof error === 'object' && 'detail' in error
      ? JSON.stringify((error as { detail: unknown }).detail)
      : undefined
  return new ApiError({ title: 'Request failed', status, detail })
}

/** A small, fully typed wrapper over the endpoints the web app uses. */
export function createGridshiftClient(baseUrl: string, fetchImpl?: typeof fetch) {
  const client = createClient<paths>({
    baseUrl: baseUrl.replace(/\/$/, ''),
    ...(fetchImpl ? { fetch: fetchImpl } : {}),
  })

  async function unwrap<T>(
    call: Promise<{ data?: T; error?: unknown; response: Response }>,
  ): Promise<T> {
    let result: { data?: T; error?: unknown; response: Response }
    try {
      result = await call
    } catch {
      throw new ApiError({
        title: 'Network error',
        status: 0,
        detail: 'Could not reach the GridShift API.',
      })
    }
    if (result.error !== undefined || result.data === undefined) {
      throw toApiError(result.error, result.response.status)
    }
    return result.data
  }

  return {
    zones: () => unwrap(client.GET('/v1/zones')),
    intensity: (zone: string) =>
      unwrap(client.GET('/v1/intensity/{zone}', { params: { path: { zone } } })),
    schedule: (body: ScheduleRequest) => unwrap(client.POST('/v1/schedule', { body })),
  }
}

export type GridshiftClient = ReturnType<typeof createGridshiftClient>
