import { useState } from 'react'
import { api, messageFor } from '../services/api'
import { ErrorMessage } from './Feedback'

export function NotifyAssignment({ id, onSent, onBusy }: { id: number; onSent: () => void; onBusy?: (busy: boolean) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<{ provider: string; action_url: string }>()
  async function send() {
    if (busy) return
    setBusy(true); onBusy?.(true); setError(''); setResult(undefined)
    try { setResult(await api.notifyAssignment(id)); onSent() }
    catch (e) { setError(messageFor(e)) }
    finally { setBusy(false); onBusy?.(false) }
  }
  return <div className="assignment-notify">
    <button className="button button-primary" disabled={busy} onClick={send}>{busy ? 'Invio…' : 'Invia Telegram'}</button>
    {error && <ErrorMessage message={error} />}
    {result && <div role="status"><p>{result.provider === 'mock' ? 'Invio simulato: nessun messaggio Telegram inviato.' : 'Notifica inviata a Telegram. Lettura non verificata.'}</p><a href={result.action_url} target="_blank" rel="noopener noreferrer">Apri link tecnico</a></div>}
  </div>
}
