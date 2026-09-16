import { useRef, useState } from 'react'
import { api, messageFor } from '../services/api'
import { demoReminderUserId } from '../services/demo'
import { OperatorDialog } from './OperatorDialog'
import { ErrorMessage } from './Feedback'

export function ReminderAction({ id, onChanged, compact = false, disabled = false, onBusy }: {
  id: number; onChanged: () => void; compact?: boolean; disabled?: boolean; onBusy?: (busy: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const userId = demoReminderUserId()
  return <div className="reminder-action">
    <button type="button" className={`button ${compact ? 'button-quiet' : 'button-primary'}`} disabled={disabled || busy || !userId} onClick={() => { setText(''); setError(''); setMessage(''); setOpen(true) }}>{compact ? 'Sollecito' : 'Aggiungi sollecito'}</button>
    {!userId && <small>Solleciti non disponibili: utente demo non configurato.</small>}
    {message && <p className="notice notice-success" role="status">{message}</p>}
    {open && <OperatorDialog label="Aggiungi sollecito" busy={busy} onClose={() => setOpen(false)}>
      <h2>Aggiungi sollecito</h2>
      <form onSubmit={async event => {
        event.preventDefault()
        if (lock.current || !userId || !text.trim() || text.trim().length > 2000) return
        lock.current = true; setBusy(true); onBusy?.(true); setError('')
        try {
          await api.addReminder(id, userId, text.trim())
          setOpen(false); setText(''); setMessage('Sollecito aggiunto.'); onChanged()
        } catch (error) { setError(messageFor(error)) }
        finally { lock.current = false; setBusy(false); onBusy?.(false) }
      }}>
        <label>Motivo / informazioni del sollecito<textarea required maxLength={2000} rows={4} disabled={busy} value={text} placeholder="Es. L'utente chiede aggiornamenti dopo il sopralluogo del tecnico." onChange={event => setText(event.target.value)} /></label>
        <div className="heading-actions"><button type="button" className="button button-secondary" disabled={busy} onClick={() => setOpen(false)}>Annulla</button><button className="button button-primary" disabled={busy || !userId || !text.trim()}>Aggiungi sollecito</button></div>
      </form>
      {error && <ErrorMessage message={error} />}
    </OperatorDialog>}
  </div>
}
