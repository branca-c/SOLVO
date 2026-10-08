// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { connectRealtime, websocketUrl } from '../services/realtime'
import { Dashboard } from '../pages/Dashboard'
import { WorkOrderDetail } from '../pages/WorkOrderDetail'
import { api } from '../services/api'
import { clearDemoAccessKey, setDemoAccessKey } from '../services/demoAccess'
import { clearDemoSessionToken, setDemoSessionToken } from '../services/demoSession'
import { order } from './fixtures'

class Socket {
  static instances: Socket[] = []
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  close = vi.fn()
  send = vi.fn()
  constructor(public url: string) { Socket.instances.push(this) }
  emit(id: number) { this.onmessage?.({ data: JSON.stringify({ type: 'assignment.accepted', work_order_id: id, timestamp: '2026-09-08T00:00:00Z' }) }) }
}
beforeEach(() => { Socket.instances = []; vi.stubGlobal('WebSocket', Socket) })
afterEach(() => { cleanup(); clearDemoAccessKey(); clearDemoSessionToken(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('derives WS/WSS URLs and reconnects with delay, then cleans up', () => {
  vi.useFakeTimers()
  expect(websocketUrl('http://localhost:5173')).toBe('ws://localhost:5173/ws/work-orders')
  expect(websocketUrl('https://solvo.example')).toBe('wss://solvo.example/ws/work-orders')
  const event = vi.fn(), status = vi.fn(), opened = vi.fn()
  const stop = connectRealtime(event, status, opened)
  const first = Socket.instances[0]
  expect(first.url).toContain('/ws/work-orders')
  first.onopen?.()
  expect(status).toHaveBeenCalledWith('Live')
  first.emit(1)
  expect(event).toHaveBeenCalledTimes(1)
  first.onmessage?.({ data: 'not JSON' })
  first.onmessage?.({ data: JSON.stringify({ type: 'unknown', work_order_id: 1 }) })
  expect(event).toHaveBeenCalledTimes(1)
  first.onclose?.()
  expect(status).toHaveBeenCalledWith('Riconnessione…')
  vi.advanceTimersByTime(2999)
  expect(Socket.instances).toHaveLength(1)
  vi.advanceTimersByTime(1)
  expect(Socket.instances).toHaveLength(2)
  Socket.instances[1].onopen?.()
  expect(opened).toHaveBeenCalledTimes(2)
  stop()
  vi.advanceTimersByTime(30000)
  expect(Socket.instances).toHaveLength(2)
  expect(Socket.instances[1].close).toHaveBeenCalled()
})

it('sends the demo key only as the first WebSocket frame, never in the URL', () => {
  setDemoAccessKey('session-only-key')
  const event = vi.fn(), status = vi.fn(), opened = vi.fn()
  connectRealtime(event, status, opened)
  const socket = Socket.instances[0]
  socket.onopen?.()
  expect(socket.url).not.toContain('session-only-key')
  expect(socket.send).toHaveBeenCalledWith('session-only-key')
  expect(opened).not.toHaveBeenCalled()
  socket.onmessage?.({ data: 'authorized' })
  expect(opened).toHaveBeenCalledOnce()
})

it('sends the session token only after the demo-key acknowledgement', () => {
  setDemoAccessKey('demo-key')
  setDemoSessionToken('exclusive-session-token')
  const opened = vi.fn()
  connectRealtime(vi.fn(), vi.fn(), opened)
  const socket = Socket.instances[0]
  socket.onopen?.()
  expect(socket.url).not.toContain('exclusive-session-token')
  expect(socket.send).toHaveBeenNthCalledWith(1, 'demo-key')
  socket.onmessage?.({ data: 'demo-key-authorized' })
  expect(socket.send).toHaveBeenNthCalledWith(2, 'exclusive-session-token')
  expect(opened).not.toHaveBeenCalled()
  socket.onmessage?.({ data: 'authorized' })
  expect(opened).toHaveBeenCalledOnce()
})

it('dashboard refetches on events and connection establishment', async () => {
  const list = vi.spyOn(api, 'list').mockResolvedValue([order])
  render(<Dashboard />)
  await screen.findByText(order.code)
  act(() => Socket.instances[0].onopen?.())
  await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
  act(() => { Socket.instances[0].emit(order.id); Socket.instances[0].emit(order.id) })
  await waitFor(() => expect(list).toHaveBeenCalledTimes(3))
  expect(Socket.instances).toHaveLength(1)
})

it('detail only refetches matching ODL and refreshes every activity section', async () => {
  const notes = vi.spyOn(api, 'notes').mockResolvedValue([])
  const get = vi.spyOn(api, 'get').mockResolvedValue(order)
  const reminders = vi.spyOn(api, 'reminders').mockResolvedValue([])
  const history = vi.spyOn(api, 'history').mockResolvedValue([])
  const assignments = vi.spyOn(api, 'assignments').mockResolvedValue([])
  render(<WorkOrderDetail id={order.id} />)
  await screen.findByText('Nessun tecnico ancora assegnato.')
  act(() => Socket.instances[0].emit(order.id + 100))
  await new Promise(resolve => setTimeout(resolve, 200))
  expect(get).toHaveBeenCalledTimes(1)
  act(() => Socket.instances[0].emit(order.id))
  await waitFor(() => {
    expect(get).toHaveBeenCalledTimes(2)
    expect(reminders).toHaveBeenCalledTimes(2)
    expect(history).toHaveBeenCalledTimes(2)
    expect(assignments).toHaveBeenCalledTimes(2)
    expect(notes).toHaveBeenCalledTimes(2)
  })
})
