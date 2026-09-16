import { ReminderAction } from './ReminderAction'
import { OperatorDialog } from './OperatorDialog'
import { useRef, useState } from 'react'
import { api, messageFor } from '../services/api'
import { navigate } from '../services/navigation'
import { useCategories } from '../hooks/useCategories'
import { priorities, type WorkOrder, type WorkOrderInput } from '../types/workOrder'
import { ErrorMessage } from './Feedback'
import { ContactFields } from './ContactFields'
function EditOrder({ order, busy, save, cancel }: { order: WorkOrder; busy: boolean; save: (data: WorkOrderInput) => void; cancel: () => void }) {
  const categories = useCategories()
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(Object.entries(order).map(([key, value]) => [key, String(value ?? '')])))
  const change = (field: string, value: string) => setValues(v => ({ ...v, [field]: value }))
  return <form onSubmit={e => { e.preventDefault(); save({ user_first_name: values.user_first_name, user_last_name: values.user_last_name, user_phone: values.user_phone, user_email: values.user_email || null, fault_address: values.fault_address, category_id: Number(values.category_id), priority: values.priority as WorkOrderInput['priority'], description: values.description }) }}>
    <fieldset disabled={busy}><legend>Modifica ODL · {order.code}</legend><div className="form-grid">
      <ContactFields values={values} onChange={change} prefix="user_" />
      <label>Indirizzo del guasto *<input required maxLength={500} value={values.fault_address} onChange={e => change('fault_address', e.target.value)} /></label>
      <label>Categoria *<select required value={values.category_id} onChange={e => change('category_id', e.target.value)}>{categories.data?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label>Priorità *<select value={values.priority} onChange={e => change('priority', e.target.value)}>{priorities.map(p => <option key={p}>{p}</option>)}</select></label>
      <label>Descrizione del guasto *<textarea required rows={4} value={values.description} onChange={e => change('description', e.target.value)} /></label>
    </div>{categories.error && <ErrorMessage message={categories.error} retry={categories.reload} />}
    <div className="heading-actions"><button type="button" className="button button-secondary" onClick={cancel}>Annulla</button><button className="button button-primary" disabled={categories.loading || !categories.data?.length}>Salva modifiche</button></div></fieldset>
  </form>
}
export function WorkOrderActions({ order, onChanged, detail = false }: { order: WorkOrder; onChanged: () => void; detail?: boolean }) {
  const [mode, setMode] = useState<'edit' | 'delete'>()
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const [feedback, setFeedback] = useState<{ message?: string; error?: string }>()
  async function act(action: () => Promise<unknown>, message: string, deleted = false) {
    if (lock.current) return
    lock.current = true; setBusy(true); setFeedback(undefined)
    try { await action(); setMode(undefined); setFeedback({ message }); onChanged(); if (deleted && detail) navigate('/odl') }
    catch (error) { setFeedback({ error: messageFor(error) }) }
    finally { lock.current = false; setBusy(false) }
  }
  return <div className="odl-actions" onClick={e => e.stopPropagation()}>
    <div className="heading-actions">{!detail && <a className="button button-quiet" href={`#/odl/${order.id}`}>Dettaglio</a>}
      <button className="button button-quiet" disabled={busy} onClick={() => { setFeedback(undefined); setMode('edit') }}>Modifica ODL</button>
      {!detail && <ReminderAction id={order.id} compact disabled={busy} onBusy={setBusy} onChanged={onChanged} />}
      <button className="button button-quiet" disabled={busy} onClick={() => { setFeedback(undefined); setMode('delete') }}>Elimina</button>
    </div>
    {feedback?.message && <p className="notice notice-success" role="status">{feedback.message}</p>}
    {mode && <OperatorDialog busy={busy} onClose={() => setMode(undefined)} label={mode === 'edit' ? 'Modifica ODL' : 'Conferma eliminazione'}>
      {mode === 'edit' ? <EditOrder order={order} busy={busy} cancel={() => setMode(undefined)} save={data => act(() => api.update(order.id, data), 'ODL aggiornato.')} /> : <><h2>Eliminare {order.code}?</h2><p>L’ODL e i suoi dati collegati saranno eliminati definitivamente.</p><div className="heading-actions"><button className="button button-secondary" disabled={busy} onClick={() => setMode(undefined)}>Annulla</button><button className="button button-primary" disabled={busy} onClick={() => act(() => api.delete(order.id), 'ODL eliminato.', true)}>Conferma eliminazione</button></div></>}
      {feedback?.error && <ErrorMessage message={feedback.error} />}
    </OperatorDialog>}
    {!mode && feedback?.error && <ErrorMessage message={feedback.error} />}
  </div>
}
