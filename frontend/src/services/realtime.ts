import { realtimeUrl } from './backendUrl'
import { getDemoAccessKey } from './demoAccess'

export const eventTypes = [
  'work_order.created', 'work_order.updated', 'work_order.deleted', 'work_order.status_changed',
  'reminder.created', 'assignment.created', 'assignment.accepted', 'assignment.rejected',
  'assignment.no_response', 'assignment.escalated', 'assignment.notification_sent',
] as const
export interface RealtimeEvent { type: typeof eventTypes[number]; work_order_id: number; timestamp: string }
export type ConnectionStatus = 'Live' | 'Riconnessione…' | 'Offline'

export const websocketUrl = realtimeUrl

export function connectRealtime(onEvent: (event: RealtimeEvent) => void, onStatus: (status: ConnectionStatus) => void, onOpen: () => void) {
  let socket: WebSocket | undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  let stopped = false
  let delay = 3000
  function retry() {
    if (stopped || timer) return
    onStatus('Riconnessione…')
    timer = setTimeout(() => { timer = undefined; connect() }, delay)
    delay = Math.min(delay * 2, 15000)
  }
  function connect() {
    if (stopped) return
    if (typeof WebSocket === 'undefined') { onStatus('Offline'); return }
    try {
      const connection = new WebSocket(websocketUrl())
      socket = connection
      connection.onopen = () => {
        if (stopped || socket !== connection) return
        const key = getDemoAccessKey()
        if (key) {
          connection.send(key)
          return
        }
        delay = 3000; onStatus('Live'); onOpen()
      }
      connection.onmessage = message => {
        if (stopped || socket !== connection) return
        if (message.data === 'authorized') {
          delay = 3000; onStatus('Live'); onOpen()
          return
        }
        let value: unknown
        try { value = JSON.parse(message.data) } catch { return }
        if (!value || typeof value !== 'object') return
        const event = value as RealtimeEvent
        if (eventTypes.includes(event.type) && Number.isSafeInteger(event.work_order_id) && event.work_order_id > 0 && typeof event.timestamp === 'string') onEvent(event)
      }
      connection.onclose = () => { if (socket === connection) retry() }
      connection.onerror = () => { connection.close(); if (socket === connection) retry() }
    } catch { retry() }
  }
  connect()
  return () => {
    stopped = true
    clearTimeout(timer)
    if (socket) {
      socket.onopen = null; socket.onmessage = null; socket.onerror = null; socket.onclose = null
      socket.close()
    }
  }
}
