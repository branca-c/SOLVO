import { api } from '../services/api'
import { useResource } from '../hooks/useResource'
import { PageHeading } from '../components/PageHeading'
import { Empty, ErrorMessage, Loading } from '../components/Feedback'

const load = (signal: AbortSignal) => api.technicians(undefined, signal)
export function Technicians() {
  const resource = useResource(load)
  return <>
    <PageHeading title="Tecnici" description="Configurazione di instradamento: tecnici in ordine di escalation, poi caposquadra." create={false} refresh={resource.reload} />
    <section className="surface">
      {resource.loading ? <Loading text="Caricamento tecnici…" /> : resource.error ? <ErrorMessage message={resource.error} retry={resource.reload} /> : !resource.data?.length ? <Empty title="Nessun tecnico configurato" text="Non sono presenti tecnici da mostrare." /> :
        <div className="table-container"><table className="odl-table"><caption className="sr-only">Tecnici e ordine di instradamento</caption>
          <thead><tr>{['Nome', 'Categoria', 'Ordine escalation', 'Ruolo', 'Telefono'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
          <tbody>{resource.data.map(item => <tr key={item.id}>
            <td data-label="Nome">{item.first_name} {item.last_name}</td><td data-label="Categoria">{item.category_name}</td>
            <td data-label="Ordine escalation">{item.escalation_order}</td><td data-label="Ruolo">{item.is_team_leader ? 'Caposquadra' : 'Tecnico'}</td>
            <td data-label="Telefono">{item.phone}</td>
          </tr>)}</tbody>
        </table></div>}
    </section>
  </>
}
