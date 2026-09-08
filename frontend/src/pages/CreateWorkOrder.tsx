import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { api, messageFor } from '../services/api'
import { navigate } from '../services/navigation'
import { priorities, type Priority, type WorkOrderDraft } from '../types/workOrder'
import { PageHeading } from '../components/PageHeading'
import { ErrorMessage } from '../components/Feedback'
import { Icon } from '../components/Icon'
import { AITextIntake } from '../components/AITextIntake'
export function CreateWorkOrder({ onCreated }: { onCreated: (id: number) => void }) {
  const [mode, setMode] = useState<'manual' | 'ai'>('manual')
  const [sourceText, setSourceText] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState('')
  const [draft, setDraft] = useState<WorkOrderDraft>()
  const [values, setValues] = useState({
    user_first_name: '', user_last_name: '', user_phone: '', user_email: '',
    fault_address: '', category_id: '', priority: 'MEDIA', description: '',
  })
  const analysis = useRef<AbortController | null>(null)
  useEffect(() => () => analysis.current?.abort(), [])
  function field(name: keyof typeof values) {
    return { name, value: values[name], onChange: (event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
      setValues(current => ({ ...current, [name]: event.target.value }))
    } }
  }
  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (analyzing || busy || !sourceText.trim()) return
    const controller = new AbortController()
    analysis.current = controller
    setAnalyzing(true); setAnalysisError(''); setError('')
    try {
      const result = await api.draft(sourceText, controller.signal)
      if (controller.signal.aborted) return
      setDraft(result)
      setValues({
        user_first_name: result.user_first_name ?? '', user_last_name: result.user_last_name ?? '',
        user_phone: result.user_phone ?? '', user_email: result.user_email ?? '',
        fault_address: result.fault_address ?? '', category_id: result.category_id?.toString() ?? '',
        priority: result.priority ?? '', description: result.description,
      })
    } catch (e) { if (!controller.signal.aborted) setAnalysisError(messageFor(e)) }
    finally { if (!controller.signal.aborted) setAnalyzing(false) }
  }
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy || analyzing || (mode === 'ai' && !draft)) return
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
    <div className="intake-modes" role="group" aria-label="Modalità di inserimento">
      <button className={mode === 'manual' ? 'mode-button selected' : 'mode-button'} type="button"
        aria-pressed={mode === 'manual'} disabled={busy || analyzing} onClick={() => setMode('manual')}>Inserimento manuale</button>
      <button className={mode === 'ai' ? 'mode-button selected' : 'mode-button'} type="button"
        aria-pressed={mode === 'ai'} disabled={busy || analyzing} onClick={() => setMode('ai')}><span aria-hidden="true">✦</span> Assistito da AI</button>
    </div>
    {mode === 'ai' && <>
      <AITextIntake text={sourceText} onTextChange={setSourceText} onAnalyze={analyze} busy={analyzing || busy} error={analysisError} />
      {draft && <div className="notice ai-review" role="status"><div>
        <strong>Bozza pronta: rivedi e conferma i dati.</strong>
        <p>Puoi modificare tutti i campi. Una nuova analisi sostituirà i valori del form.</p>
        {draft.category_name && <p>Categoria proposta: {draft.category_name}.</p>}
        {draft.warnings.length > 0 && <ul>{draft.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}
      </div></div>}
    </>}
    {(mode === 'manual' || draft) && <form className="surface create-form" onSubmit={submit} aria-busy={busy}>
      <div className="section-heading"><div><h2>Dettagli della richiesta</h2><p>I campi contrassegnati con * sono obbligatori.</p></div><span className="form-step">Nuovo ODL</span></div>
      {error && <ErrorMessage message={error} />}
      <fieldset disabled={busy || analyzing}><legend>Richiedente</legend><div className="form-grid">
        <label>Nome *<input {...field('user_first_name')} required maxLength={100} autoComplete="given-name" /></label>
        <label>Cognome *<input {...field('user_last_name')} required maxLength={100} autoComplete="family-name" /></label>
        <label>Telefono *<input {...field('user_phone')} type="tel" required maxLength={32} autoComplete="tel" /></label>
        <label>Email <span className="optional">(facoltativa)</span><input {...field('user_email')} type="email" maxLength={255} autoComplete="email" /></label>
      </div></fieldset>
      <fieldset disabled={busy || analyzing}><legend>Intervento</legend><div className="form-grid">
        <label className="full-width">Indirizzo del guasto *<input {...field('fault_address')} required maxLength={500} autoComplete="street-address" placeholder="Via, numero civico, edificio o locale" /></label>
        <div className="field"><label htmlFor="category-id">ID categoria *</label><input id="category-id" {...field('category_id')} type="number" required min="1" step="1" aria-describedby="category-help" /><small id="category-help">Inserisci l’ID di una categoria già configurata.</small></div>
        <label><span id="create-priority-label">Priorità *</span><select aria-labelledby="create-priority-label" {...field('priority')} required><option value="" disabled>Seleziona una priorità</option>{priorities.map(p => <option key={p}>{p}</option>)}</select></label>
        <label className="full-width">Descrizione del guasto *<textarea {...field('description')} required rows={5} placeholder="Descrivi il problema e indica i dettagli utili all’intervento." /></label>
      </div></fieldset>
      <div className="form-footer"><p>L’ODL sarà creato con stato <strong>APERTO</strong>.</p><div className="heading-actions"><button type="button" className="button button-secondary" disabled={busy || analyzing} onClick={() => navigate('/odl')}>Annulla</button><button className="button button-primary" disabled={busy || analyzing} type="submit"><Icon name="plus" />{busy ? 'Creazione…' : mode === 'ai' ? 'Conferma e crea ODL' : 'Crea ODL'}</button></div></div>
    </form>}
  </>
}
