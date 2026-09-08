import { useEffect, useState } from 'react'
import { messageFor } from '../services/api'

export function useResource<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true })
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setState(current => ({ data: current.data, loading: true }))
    load(controller.signal).then(
      data => { if (!controller.signal.aborted) setState({ data, loading: false }) },
      error => { if (!controller.signal.aborted) setState({ error: messageFor(error), loading: false }) },
    )
    return () => controller.abort()
  }, [load, version])
  return { ...state, reload: () => setVersion(v => v + 1) }
}
