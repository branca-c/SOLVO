import { CategoryName } from './CategoryName'
import { NotifyAssignment } from './NotifyAssignment'
import { useCallback, useRef, useState } from 'react'
import { api, messageFor } from '../services/api'
import { formatDate } from '../services/format'
import { useResource } from '../hooks/useResource'
import { assignmentLabels, type WorkOrderStatus } from '../types/workOrder'
import { ErrorMessage, Loading } from './Feedback'

const eventLabels: Record<string, string> = {
  ASSIGNMENT_NOTIFICATION_SENT: 'Notifica assegnazione',
  CREATED: 'ODL creato', STATUS_CHANGED: 'Stato aggiornato', REMINDER_CREATED: 'Sollecito ricevuto',
  ASSIGNMENT_STARTED: 'Assegnazione avviata', ASSIGNMENT_ACCEPTED: 'Assegnazione accettata',
  ASSIGNMENT_REJECTED: 'Assegnazione rifiutata', ASSIGNMENT_NO_RESPONSE: 'Nessuna risposta', ASSIGNMENT_ESCALATED: 'Escalation al caposquadra',
}
export function ActivityPanels({ id, status, onChanged, refreshVersion = 0 }: {
  id: number; status: WorkOrderStatus; onChanged: () => void; refreshVersion?: number
}) {
  const terminal = status === 'CHIUSO' || status === 'ANNULLATO'
  const demoValue = String(import.meta.env.VITE_DEMO_USER_ID ?? '').trim()
  const demoUserId = /^[1-9]\d*$/.test(demoValue) && Number.isSafeInteger(Number(demoValue)) ? Number(demoValue) : undefined
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const [feedback, setFeedback] = useState<{ section: 'assignment' | 'reminder'; message?: string; error?: string }>()
  async function act(section: 'assignment' | 'reminder', action: () => Promise<unknown>, message: string) {
    if (lock.current) return
    lock.current = true
    setBusy(true); setFeedback(undefined)
    try {
      await action()
      setFeedback({ section, message })
      onChanged()
    } catch (error) {
      setFeedback({ section, error: messageFor(error) })
      // Refetch authoritative state after conflicts; never retry the mutation.
      onChanged()
    } finally { lock.current = false; setBusy(false) }
  }
  const reminders = useResource(useCallback((signal: AbortSignal) => api.reminders(id, signal), [id, refreshVersion]))
  const history = useResource(useCallback((signal: AbortSignal) => api.history(id, signal), [id, refreshVersion]))
  const assignments = useResource(useCallback((signal: AbortSignal) => api.assignments(id, signal), [id, refreshVersion]))
  const current = assignments.data?.find(item => item.status === 'PENDING') ?? assignments.data?.at(-1)
  return <div className="activity-grid">
    <section className="surface"><div className="section-heading"><h2>Storico attività</h2><span className="count">{history.data?.length ?? '—'}</span></div>
      {history.loading && !history.data ? <Loading text="Caricamento storico…" /> : history.error ? <ErrorMessage message={history.error} retry={history.reload} /> : !history.data?.length ? <p className="section-empty">Nessuna attività registrata.</p> : <ol className="timeline">{history.data.map(entry => <li key={entry.id}><span className="timeline-dot" /><div><strong>{eventLabels[entry.event_type] || entry.event_type}</strong><p>{entry.description}</p><time dateTime={entry.created_at}>{formatDate(entry.created_at, true)}</time></div></li>)}</ol>}
    </section>
    <div className="activity-side">
      <section className="surface" aria-labelledby="assignments-heading"><div className="section-heading"><h2 id="assignments-heading">Assegnazioni</h2><span className="count">{assignments.data?.length ?? '—'}</span></div>
        {feedback?.section === 'assignment' && <>{feedback.error ? <ErrorMessage message={feedback.error} /> : <p className="notice notice-success" role="status">{feedback.message}</p>}</>}
        {!terminal && assignments.data?.length === 0 && !assignments.error && <div className="section-heading"><button type="button" className="button button-primary" disabled={busy || assignments.loading} onClick={() => act('assignment', () => api.startAssignment(id), 'Assegnazione avviata.')}>Assegna tecnico</button></div>}
        {assignments.loading && !assignments.data ? <Loading text="Caricamento assegnazioni…" /> : assignments.error ? <ErrorMessage message={assignments.error} retry={assignments.reload} /> : !assignments.data?.length ? <p className="section-empty">Nessun tecnico ancora assegnato.</p> : <ol className="record-list">{assignments.data.map(item => <li key={item.id}><div className="record-heading"><strong>{item.technician.first_name} {item.technician.last_name}</strong><span className="badge badge-neutral">{item.status === 'PENDING' || item.status === 'ACCEPTED' ? item.status : assignmentLabels[item.status]}</span></div>{item.id === current?.id && <p><strong>Assegnazione corrente / ultima</strong></p>}<p><CategoryName id={item.technician.category_id} /></p><p>Tentativo {item.attempt_number}{item.technician.is_team_leader ? ' · Caposquadra' : ''}</p><time dateTime={item.sent_at}>{formatDate(item.sent_at, true)}</time>{item.responded_at && <p>Risposta: {formatDate(item.responded_at, true)}</p>}{item.id === current?.id && item.status === 'PENDING' && !terminal && <fieldset className="operator-actions" disabled={busy || assignments.loading}>
          <legend className="sr-only">Azioni assegnazione corrente</legend>
          <NotifyAssignment id={item.id} onSent={history.reload} onBusy={setBusy} />
          <div className="heading-actions"><button type="button" className="button button-secondary" onClick={() => act('assignment', () => api.noResponse(item.id), 'Nessuna risposta registrata. Assegnazione avanzata.')}>Nessuna risposta</button>
          <button type="button" className="button button-secondary" onClick={() => act('assignment', () => api.escalateTeamLeader(id), 'Escalation al caposquadra avviata.')}>Escala al caposquadra</button></div>
        </fieldset>}{item.rejection_notes && <p className="record-notes">{item.rejection_notes}</p>}</li>)}</ol>}
      </section>
      <section className="surface" aria-labelledby="reminders-heading"><div className="section-heading"><h2 id="reminders-heading">Solleciti</h2><span className="count">{reminders.data?.length ?? '—'}</span></div>
        <div className="section-heading"><button type="button" className="button button-primary" disabled={busy || reminders.loading || !demoUserId} onClick={() => demoUserId && act('reminder', () => api.addReminder(id, demoUserId), 'Sollecito aggiunto.')}>Aggiungi sollecito</button></div>
        {!demoUserId && <p className="section-empty">Solleciti non disponibili: utente demo non configurato.</p>}
        {feedback?.section === 'reminder' && <>{feedback.error ? <ErrorMessage message={feedback.error} /> : <p className="notice notice-success" role="status">{feedback.message}</p>}</>}
        {reminders.loading && !reminders.data ? <Loading text="Caricamento solleciti…" /> : reminders.error ? <ErrorMessage message={reminders.error} retry={reminders.reload} /> : !reminders.data?.length ? <p className="section-empty">Nessun sollecito ricevuto.</p> : <ol className="record-list">{reminders.data.map(item => <li key={item.id}><strong>Sollecito #{item.id}</strong><p>Inserito da utente #{item.created_by}</p><time dateTime={item.created_at}>{formatDate(item.created_at, true)}</time></li>)}</ol>}
      </section>
    </div>
  </div>
}
