import { useCallback } from 'react'
import { api } from '../services/api'
import { formatDate } from '../services/format'
import { useResource } from '../hooks/useResource'
import { assignmentLabels } from '../types/workOrder'
import { ErrorMessage, Loading } from './Feedback'

const eventLabels: Record<string, string> = {
  CREATED: 'ODL creato', STATUS_CHANGED: 'Stato aggiornato', REMINDER_CREATED: 'Sollecito ricevuto',
  ASSIGNMENT_STARTED: 'Assegnazione avviata', ASSIGNMENT_ACCEPTED: 'Assegnazione accettata',
  ASSIGNMENT_REJECTED: 'Assegnazione rifiutata', ASSIGNMENT_NO_RESPONSE: 'Nessuna risposta', ASSIGNMENT_ESCALATED: 'Escalation al caposquadra',
}
export function ActivityPanels({ id }: { id: number }) {
  const reminders = useResource(useCallback((signal: AbortSignal) => api.reminders(id, signal), [id]))
  const history = useResource(useCallback((signal: AbortSignal) => api.history(id, signal), [id]))
  const assignments = useResource(useCallback((signal: AbortSignal) => api.assignments(id, signal), [id]))
  return <div className="activity-grid">
    <section className="surface"><div className="section-heading"><h2>Storico attività</h2><span className="count">{history.data?.length ?? '—'}</span></div>
      {history.loading ? <Loading text="Caricamento storico…" /> : history.error ? <ErrorMessage message={history.error} retry={history.reload} /> : !history.data?.length ? <p className="section-empty">Nessuna attività registrata.</p> : <ol className="timeline">{history.data.map(entry => <li key={entry.id}><span className="timeline-dot" /><div><strong>{eventLabels[entry.event_type] || entry.event_type}</strong><p>{entry.description}</p><time dateTime={entry.created_at}>{formatDate(entry.created_at, true)}</time></div></li>)}</ol>}
    </section>
    <div className="activity-side">
      <section className="surface"><div className="section-heading"><h2>Assegnazioni</h2><span className="count">{assignments.data?.length ?? '—'}</span></div>
        {assignments.loading ? <Loading text="Caricamento assegnazioni…" /> : assignments.error ? <ErrorMessage message={assignments.error} retry={assignments.reload} /> : !assignments.data?.length ? <p className="section-empty">Nessun tecnico ancora assegnato.</p> : <ol className="record-list">{assignments.data.map(item => <li key={item.id}><div className="record-heading"><strong>{item.technician.first_name} {item.technician.last_name}</strong><span className="badge badge-neutral">{assignmentLabels[item.status]}</span></div><p>Tentativo {item.attempt_number}{item.technician.is_team_leader ? ' · Caposquadra' : ''}</p><time dateTime={item.sent_at}>{formatDate(item.sent_at, true)}</time>{item.responded_at && <p>Risposta: {formatDate(item.responded_at, true)}</p>}{item.rejection_notes && <p className="record-notes">{item.rejection_notes}</p>}</li>)}</ol>}
      </section>
      <section className="surface"><div className="section-heading"><h2>Solleciti</h2><span className="count">{reminders.data?.length ?? '—'}</span></div>
        {reminders.loading ? <Loading text="Caricamento solleciti…" /> : reminders.error ? <ErrorMessage message={reminders.error} retry={reminders.reload} /> : !reminders.data?.length ? <p className="section-empty">Nessun sollecito ricevuto.</p> : <ol className="record-list">{reminders.data.map(item => <li key={item.id}><strong>Sollecito #{item.id}</strong><p>Inserito da utente #{item.created_by}</p><time dateTime={item.created_at}>{formatDate(item.created_at, true)}</time></li>)}</ol>}
      </section>
    </div>
  </div>
}
