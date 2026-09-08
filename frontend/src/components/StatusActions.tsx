import { useState, type FormEvent } from 'react'
import { api, messageFor } from '../services/api'
import { transitions, statusLabels, type WorkOrder } from '../types/workOrder'
import { ErrorMessage } from './Feedback'
export function StatusActions({ order, onChanged }: { order: WorkOrder; onChanged: (message: string) => void }) {
  const available = transitions[order.status]
  const [next, setNext] = useState<string>(available[0] || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault()
    const target = available.find(s => s === next)
    if (!target || busy) return
    setBusy(true); setError('')
    try {
      await api.status(order.id, target)
      onChanged(`Stato aggiornato: ${statusLabels[target]}.`)
    } catch (e) { setError(messageFor(e)) }
    finally { setBusy(false) }
  }
  return <section className="surface status-actions"><div><h2>Aggiorna stato</h2><p>{available.length ? 'Seleziona il prossimo stato dell’ordine di lavoro.' : 'Questo ODL è concluso. Non sono disponibili ulteriori cambi di stato.'}</p></div>{available.length > 0 && <form onSubmit={submit}><label><span id="next-status-label">Nuovo stato</span><select aria-labelledby="next-status-label" value={next} onChange={e => setNext(e.target.value)} disabled={busy}>{available.map(s => <option key={s} value={s}>{statusLabels[s]}</option>)}</select></label><button className="button button-primary" disabled={busy} type="submit">{busy ? 'Aggiornamento…' : 'Applica stato'}</button></form>}{error && <ErrorMessage message={error} />}</section>
}
