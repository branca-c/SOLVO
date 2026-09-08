import type { ConnectionStatus } from '../services/realtime'

export function RealtimeStatus({ status }: { status: ConnectionStatus }) {
  return <p className="realtime-status" role="status"><span aria-hidden="true">{status === 'Live' ? '●' : '○'}</span> {status}</p>
}
