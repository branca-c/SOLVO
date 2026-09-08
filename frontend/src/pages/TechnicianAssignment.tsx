import { useCallback, useState } from 'react'
import { PriorityBadge, StatusBadge } from '../components/Badge'
import { ErrorMessage, Loading } from '../components/Feedback'
import { useResource } from '../hooks/useResource'
import { api, ApiError, messageFor } from '../services/api'
import { assignmentLabels, type PublicAssignment } from '../types/workOrder'

export function TechnicianAssignment({ token }: { token: string }) {
  const [invalid, setInvalid] = useState(false)
  const resource = useResource(useCallback(async (signal: AbortSignal) => {
    try { const result = await api.publicAssignment(token, signal); setInvalid(false); return result }
    catch (e) { if (!signal.aborted) setInvalid(e instanceof ApiError && e.status === 404); throw e }
  }, [token]))
  const [updated, setUpdated] = useState<PublicAssignment>()
  const [rejecting, setRejecting] = useState(false)
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const assignment = updated ?? resource.data
  async function act(action: 'accept' | 'reject') {
    if (busy) return
    setBusy(true); setError('')
    try {
      setUpdated(action === 'accept' ? await api.publicAccept(token) : await api.publicReject(token, notes || null))
      setRejecting(false)
    } catch (e) { setError(messageFor(e)); if (e instanceof ApiError && e.status === 409) resource.reload() }
    finally { setBusy(false) }
  }
  return <main id="main-content" tabIndex={-1} className="technician-page">
    <header className="technician-brand"><strong>SOLVO</strong><span>Il tuo intervento</span></header>
    {resource.loading ? <Loading /> : resource.error ? <section className="surface technician-card"><h1>{invalid ? 'Link non valido o scaduto' : 'Intervento non disponibile'}</h1><ErrorMessage message={invalid ? 'Chiedi all’operatore un nuovo link.' : resource.error} retry={invalid ? undefined : resource.reload} /></section> : assignment && <section className="surface technician-card">
      <p className="eyebrow">ORDINE DI LAVORO</p><h1>{assignment.work_order_code}</h1>
      <div className="badges"><PriorityBadge value={assignment.priority} /><StatusBadge value={assignment.work_order_status} /></div>
      <p><strong>{assignment.technician_name}</strong> · {assignmentLabels[assignment.status]}</p>
      <dl><dt>Categoria</dt><dd>{assignment.category}</dd><dt>Indirizzo</dt><dd>{assignment.fault_address}</dd><dt>Richiedente</dt><dd>{assignment.requester_name}</dd><dt>Telefono</dt><dd><a href={`tel:${assignment.requester_phone}`}>{assignment.requester_phone}</a></dd></dl>
      <h2>Descrizione del guasto</h2><p className="record-notes">{assignment.description}</p>
      {assignment.status === 'ACCEPTED' && <div role="status" className="notice notice-success">Intervento accettato</div>}
      {assignment.status === 'REJECTED' && <div role="status" className="notice"><div>Intervento rifiutato<p>SOLVO ha inoltrato la richiesta al prossimo tecnico. La notifica sarà inviata dall’operatore.</p></div></div>}
      {assignment.rejection_notes && <p>Note: {assignment.rejection_notes}</p>}
      {error && <ErrorMessage message={error} />}
      {assignment.status === 'PENDING' && !['CHIUSO', 'ANNULLATO'].includes(assignment.work_order_status) ? <div className="technician-actions">
        {!rejecting ? <><button className="button button-primary" disabled={busy} onClick={() => act('accept')}>{busy ? 'Invio…' : 'Accetta intervento'}</button><button className="button button-secondary" disabled={busy} onClick={() => setRejecting(true)}>Rifiuta</button></> : <form onSubmit={event => { event.preventDefault(); void act('reject') }}>
          <label>Note del rifiuto (facoltative)<textarea rows={4} value={notes} disabled={busy} onChange={event => setNotes(event.target.value)} /></label>
          <button className="button button-secondary" type="submit" disabled={busy}>{busy ? 'Invio…' : 'Conferma rifiuto'}</button>
          <button className="button button-secondary" type="button" disabled={busy} onClick={() => setRejecting(false)}>Annulla</button>
        </form>}
      </div> : assignment.status !== 'ACCEPTED' && assignment.status !== 'REJECTED' && <p role="status">Questa assegnazione non è più disponibile per una risposta.</p>}
    </section>}
  </main>
}
