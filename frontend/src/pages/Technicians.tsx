import { TechnicianEdit } from '../components/TechnicianEdit'
import { api, messageFor } from '../services/api'
import { useResource } from '../hooks/useResource'
import { PageHeading } from '../components/PageHeading'
import { Empty, ErrorMessage, Loading } from '../components/Feedback'
import { useRef, useState } from 'react'

const load = (signal: AbortSignal) => api.technicians(undefined, signal)
export function Technicians() {
  const resource = useResource(load)
  const [linkingId, setLinkingId] = useState<number | null>(null)
  const [linkError, setLinkError] = useState('')
  const linkLock = useRef(false)
  const linkTelegram = async (id: number) => {
    if (linkLock.current) return
    linkLock.current = true
    setLinkingId(id)
    setLinkError('')
    try {
      const { url } = await api.telegramLink(id)
      window.location.assign(url)
    } catch (error) {
      setLinkError(messageFor(error))
    } finally {
      linkLock.current = false
      setLinkingId(null)
    }
  }
  return <>
    <PageHeading title="Tecnici" description="Configurazione di instradamento: tecnici in ordine di escalation, poi caposquadra." create={false} refresh={resource.reload} />
    <p className="notice">Scegli un tecnico demo non collegato e seleziona “Collega Telegram”: si aprirà il bot SOLVO. Dopo Start/Avvia, il tecnico riceverà le future notifiche Telegram. Ogni account Telegram può essere collegato a un solo tecnico.</p>
    {linkError && <ErrorMessage message={linkError} />}
    <section className="surface">
      {resource.loading && !resource.data ? <Loading text="Caricamento tecnici…" /> : resource.error ? <ErrorMessage message={resource.error} retry={resource.reload} /> : !resource.data?.length ? <Empty title="Nessun tecnico configurato" text="Non sono presenti tecnici da mostrare." /> :
        <div className="table-container"><table className="odl-table"><caption className="sr-only">Tecnici e ordine di instradamento</caption>
          <thead><tr>{['Nome', 'Categoria', 'Ordine escalation', 'Ruolo', 'Telefono', 'Email', 'Telegram', 'Azioni'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
          <tbody>{resource.data.map(item => <tr key={item.id}>
            <td data-label="Nome">{item.first_name} {item.last_name}</td><td data-label="Categoria">{item.category_name}</td>
            <td data-label="Ordine escalation">{item.escalation_order}</td><td data-label="Ruolo">{item.is_team_leader ? 'Caposquadra' : 'Tecnico'}</td>
            <td data-label="Telefono">{item.phone}</td><td data-label="Email">{item.email || '—'}</td>
            <td data-label="Telegram">{item.telegram_linked ? <span className="badge badge-neutral">Collegato</span> : <><span className="badge badge-neutral">Non collegato</span> <button className="button button-quiet" disabled={linkingId !== null} onClick={() => linkTelegram(item.id)}>{linkingId === item.id ? `Collegamento di ${item.first_name}…` : 'Collega Telegram'}</button></>}</td>
            <td data-label="Azioni"><TechnicianEdit technician={item} onChanged={resource.reload} /></td>
          </tr>)}</tbody>
        </table></div>}
    </section>
  </>
}
