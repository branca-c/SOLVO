import { useState, type FormEvent } from 'react'
import { api, messageFor } from '../services/api'
import { navigate } from '../services/navigation'
import { priorities, type Priority } from '../types/workOrder'
import { PageHeading } from '../components/PageHeading'
import { ErrorMessage } from '../components/Feedback'
import { Icon } from '../components/Icon'
export function CreateWorkOrder({ onCreated }: { onCreated: (id: number) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const form = new FormData(event.currentTarget)
    const text = (name: string) => String(form.get(name) ?? '').trim()
    setError('')
    if (['user_first_name', 'user_last_name', 'user_phone', 'fault_address', 'description'].some(name => !text(name))) {
      setError('Compila tutti i campi obbligatori con un valore valido.'); return
    }
    setBusy(true)
    try {
      const order = await api.create({
        user_first_name: text('user_first_name'), user_last_name: text('user_last_name'),
        user_phone: text('user_phone'), user_email: text('user_email') || null,
        fault_address: text('fault_address'), category_id: Number(text('category_id')),
        priority: text('priority') as Priority, description: text('description'),
      })
      onCreated(order.id)
      navigate(`/odl/${order.id}`)
    } catch (e) { setError(messageFor(e)) }
    finally { setBusy(false) }
  }
  return <>
    <a className="text-link back-link" href="#/odl">← Torna agli ODL</a>
    <PageHeading title="Nuovo ordine di lavoro" description="Inserisci i dati del richiedente e descrivi l’intervento necessario." create={false} />
    <form className="surface create-form" onSubmit={submit} aria-busy={busy}>
      <div className="section-heading"><div><h2>Dettagli della richiesta</h2><p>I campi contrassegnati con * sono obbligatori.</p></div><span className="form-step">Nuovo ODL</span></div>
      {error && <ErrorMessage message={error} />}
      <fieldset disabled={busy}><legend>Richiedente</legend><div className="form-grid">
        <label>Nome *<input name="user_first_name" required maxLength={100} autoComplete="given-name" /></label>
        <label>Cognome *<input name="user_last_name" required maxLength={100} autoComplete="family-name" /></label>
        <label>Telefono *<input name="user_phone" type="tel" required maxLength={32} autoComplete="tel" /></label>
        <label>Email <span className="optional">(facoltativa)</span><input name="user_email" type="email" maxLength={255} autoComplete="email" /></label>
      </div></fieldset>
      <fieldset disabled={busy}><legend>Intervento</legend><div className="form-grid">
        <label className="full-width">Indirizzo del guasto *<input name="fault_address" required maxLength={500} autoComplete="street-address" placeholder="Via, numero civico, edificio o locale" /></label>
        <div className="field"><label htmlFor="category-id">ID categoria *</label><input id="category-id" name="category_id" type="number" required min="1" step="1" aria-describedby="category-help" /><small id="category-help">Inserisci l’ID di una categoria già configurata.</small></div>
        <label><span id="create-priority-label">Priorità *</span><select aria-labelledby="create-priority-label" name="priority" defaultValue="MEDIA" required>{priorities.map(p => <option key={p}>{p}</option>)}</select></label>
        <label className="full-width">Descrizione del guasto *<textarea name="description" required rows={5} placeholder="Descrivi il problema e indica i dettagli utili all’intervento." /></label>
      </div></fieldset>
      <div className="form-footer"><p>L’ODL sarà creato con stato <strong>APERTO</strong>.</p><div className="heading-actions"><button type="button" className="button button-secondary" disabled={busy} onClick={() => navigate('/odl')}>Annulla</button><button className="button button-primary" disabled={busy} type="submit"><Icon name="plus" />{busy ? 'Creazione…' : 'Crea ODL'}</button></div></div>
    </form>
  </>
}
