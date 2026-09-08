import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, errorDetail } from '../services/api'
import { newestFirst, summarize } from '../services/format'
import { transitions } from '../types/workOrder'
import { order } from './fixtures'
afterEach(() => vi.unstubAllGlobals())
describe('ODL helpers', () => {
  it('counts all statuses and urgent orders without counting cancelled orders as complete', () => {
    const orders = [order, { ...order, id: 2, status: 'IN_CORSO' as const }, { ...order, id: 3, status: 'CHIUSO' as const }, { ...order, id: 4, status: 'EVASO' as const }, { ...order, id: 5, status: 'ANNULLATO' as const }]
    expect(summarize(orders)).toEqual({ total: 5, open: 1, ongoing: 1, urgent: 5, complete: 2 })
    expect(summarize([]).total).toBe(0)
  })
  it('sorts by date then ID without mutating input', () => {
    const orders = [{ ...order, id: 3, created_at: '2026-09-01T12:00:00Z' }, order, { ...order, id: 2 }]
    expect(newestFirst(orders).map(o => o.id)).toEqual([2, 1, 3])
    expect(orders[0].id).toBe(3)
  })
  it('matches the backend transition policy, including terminal states', () => {
    expect(transitions).toEqual({ APERTO: ['IN_CORSO', 'ANNULLATO'], IN_CORSO: ['EVASO', 'ANNULLATO'], EVASO: ['CHIUSO', 'IN_CORSO'], CHIUSO: [], ANNULLATO: [] })
  })
})
describe('API contracts', () => {
  it('sends filters to the real API paths', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify([order])))
    vi.stubGlobal('fetch', fetcher)
    expect(await api.list({ status: 'APERTO', priority: 'URGENTE' })).toEqual([order])
    expect(fetcher.mock.calls[0][0]).toBe('/api/work-orders?status=APERTO&priority=URGENTE')
  })
  it('sends only create fields, then status to its dedicated endpoint', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(order)))
    vi.stubGlobal('fetch', fetcher)
    await api.status(1, 'IN_CORSO')
    expect(fetcher.mock.calls[0][0]).toBe('/api/work-orders/1/status')
    expect(fetcher.mock.calls[0][1].method).toBe('PATCH')
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ status: 'IN_CORSO' })
  })
  it('handles FastAPI detail strings, validation errors, and unavailable services', async () => {
    expect(errorDetail({ detail: [{ loc: ['body', 'category_id'], msg: 'invalid' }] })).toBe('Controlla i campi: Categoria.')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Transizione non consentita' }), { status: 409 })))
    await expect(api.status(1, 'CHIUSO')).rejects.toThrow('Transizione non consentita')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api.list()).rejects.toBeInstanceOf(ApiError)
  })
  it('rejects non-JSON proxy errors without exposing HTML', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>proxy failure</html>', { status: 502 })))
    await expect(api.list()).rejects.toThrow('Impossibile completare la richiesta')
  })
})

it('uploads multipart audio without overriding the browser boundary', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ transcript: 'demo', draft: {} })))
  vi.stubGlobal('fetch', fetcher)
  const file = new File(['audio'], 'fault.wav', { type: 'audio/wav' })
  await api.audioDraft(file)
  const [path, options] = fetcher.mock.calls[0]
  expect(path).toBe('/api/ai/work-order-draft-audio')
  expect(options.body.get('audio')).toBe(file)
  expect(options.headers['Content-Type']).toBeUndefined()
})

it('uses token-scoped public action paths and the explicit notify endpoint', async () => {
  const fetcher = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ id: 1 })))
  vi.stubGlobal('fetch', fetcher)
  await api.publicAssignment('v1.token')
  await api.publicAccept('v1.token')
  await api.publicReject('v1.token', 'Note facoltative')
  await api.notifyAssignment(1)
  expect(fetcher.mock.calls.map(call => call[0])).toEqual([
    '/api/public/assignments/v1.token', '/api/public/assignments/v1.token/accept',
    '/api/public/assignments/v1.token/reject', '/api/assignments/1/notify',
  ])
  expect(fetcher.mock.calls[1][1].method).toBe('POST')
  expect(JSON.parse(fetcher.mock.calls[2][1].body)).toEqual({ rejection_notes: 'Note facoltative' })
})
