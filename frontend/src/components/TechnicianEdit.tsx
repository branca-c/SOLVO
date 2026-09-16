import { OperatorDialog } from './OperatorDialog'
import { useRef, useState } from 'react'
import type { Technician } from '../types/referenceData'
import { api, messageFor } from '../services/api'
import { ContactFields } from './ContactFields'
import { ErrorMessage } from './Feedback'
export function TechnicianEdit({ technician, onChanged }: { technician: Technician; onChanged: () => void }) {
  const [open, setOpen] = useState(false)
  const [values, setValues] = useState<Record<string, string>>({ first_name: technician.first_name, last_name: technician.last_name, phone: technician.phone, email: technician.email ?? '' })
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  return <><button className="button button-quiet" onClick={() => { setValues({ first_name: technician.first_name, last_name: technician.last_name, phone: technician.phone, email: technician.email ?? '' }); setError(''); setOpen(true) }}>Modifica</button>
    {message && <p role="status">{message}</p>}
    {open && <OperatorDialog busy={busy} onClose={() => setOpen(false)} label="Modifica tecnico"><h2>Modifica tecnico</h2>
      <p>Categoria: {technician.category_name} · Ordine escalation: {technician.escalation_order} · Ruolo: {technician.is_team_leader ? 'Caposquadra' : 'Tecnico'} (sola lettura)</p>
      <form onSubmit={async e => {
        e.preventDefault(); if (lock.current) return
        lock.current = true; setBusy(true); setError('')
        try { await api.updateTechnician(technician.id, { first_name: values.first_name, last_name: values.last_name, phone: values.phone, email: values.email || null }); setOpen(false); setMessage('Tecnico aggiornato.'); onChanged() }
        catch (error) { setError(messageFor(error)) }
        finally { lock.current = false; setBusy(false) }
      }}><fieldset disabled={busy}><div className="form-grid"><ContactFields values={values} onChange={(field, value) => setValues(v => ({ ...v, [field]: value }))} /></div><div className="heading-actions"><button type="button" className="button button-secondary" onClick={() => setOpen(false)}>Annulla</button><button className="button button-primary">Salva modifiche</button></div></fieldset></form>
      {error && <ErrorMessage message={error} />}
    </OperatorDialog>}
  </>
}
