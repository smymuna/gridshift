import { ApiError, createGridshiftClient } from './index'

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('createGridshiftClient', () => {
  it('returns typed data on success', async () => {
    const fetchImpl = vi.fn(async (_req: Request) => json(200, [{ code: 'de', name: 'Germany' }]))
    const client = createGridshiftClient('http://api.test/', fetchImpl as unknown as typeof fetch)
    expect(await client.zones()).toEqual([{ code: 'de', name: 'Germany' }])
    const req = fetchImpl.mock.calls[0][0]
    expect(req.url).toBe('http://api.test/v1/zones')
  })

  it('turns RFC 9457 problems into ApiError', async () => {
    const problem = {
      type: 'about:blank',
      title: 'Zone not found',
      status: 404,
      detail: "no data for 'xx'",
    }
    const client = createGridshiftClient('http://api.test', (async () =>
      json(404, problem)) as typeof fetch)
    await expect(client.intensity('xx')).rejects.toMatchObject({
      status: 404,
      title: 'Zone not found',
    })
  })

  it('reports network failures as status 0', async () => {
    const client = createGridshiftClient('http://api.test', (async () => {
      throw new TypeError('Failed to fetch')
    }) as typeof fetch)
    const err = await client.zones().catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(0)
  })
})
