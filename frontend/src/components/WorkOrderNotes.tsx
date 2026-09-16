import { useCallback, useRef, useState } from 'react'
import { api, messageFor } from '../services/api'
import { useResource } from '../hooks/useResource'
import { formatDate } from '../services/format'
import { ErrorMessage, Loading } from './Feedback'
export function WorkOrderNotes({ id, refreshVersion, onChanged }: { id: number; refreshVersion: number; onChanged: () => void }) {
  const notes = useResource(useCallback((signal: AbortSignal) => api.notes(id, signal), [id, refreshVersion]))
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  return <section className="surface"><div className="section-heading"><h2>Note</h2></div>
    {notes.loading && !notes.data ? <Loading text="Caricamento note…" /> : notes.error ? <ErrorMessage message={notes.error} retry={notes.reload} /> : !notes.data?.length ? <p className="section-empty">Nessuna nota presente.</p> : <ol className="record-list">{notes.data?.map(note => <li key={note.id}><p className="record-notes">{note.text}</p><time dateTime={note.created_at}>{formatDate(note.created_at, true)}</time></li>)}</ol>}
    <hr className="notes-separator" />
    <h3>Aggiungi nota</h3>
    <form className="operator-actions" onSubmit={async e => {
      e.preventDefault(); if (lock.current || !text.trim()) return
      lock.current = true; setBusy(true); setError(''); setMessage('')
      try { await api.addNote(id, text); setText(''); setMessage('Nota aggiunta.'); notes.reload(); onChanged() }
      catch (error) { setError(messageFor(error)) }
      finally { lock.current = false; setBusy(false) }
    }}><label>Nuova nota<textarea required value={text} disabled={busy} onChange={e => setText(e.target.value)} /></label><button className="button button-primary" disabled={busy || !text.trim()}>Aggiungi nota</button></form>
    {error && <ErrorMessage message={error} />}{message && <p className="notice notice-success" role="status">{message}</p>}
  </section>
}
