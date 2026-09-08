import { useEffect, useRef, useState } from 'react'
import { connectRealtime, type ConnectionStatus } from '../services/realtime'

export function useRealtime(refresh: () => void, workOrderId?: number) {
  const callback = useRef(refresh)
  callback.current = refresh
  const [status, setStatus] = useState<ConnectionStatus>('Riconnessione…')
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    const schedule = () => {
      if (timer) return
      timer = setTimeout(() => { timer = undefined; callback.current() }, 150)
    }
    const stop = connectRealtime(event => {
      if (workOrderId === undefined || event.work_order_id === workOrderId) schedule()
    }, setStatus, schedule)
    return () => { stop(); clearTimeout(timer) }
  }, [workOrderId])
  return status
}
