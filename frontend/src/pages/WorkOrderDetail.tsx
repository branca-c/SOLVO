import { useRealtime } from '../hooks/useRealtime'
import { RealtimeStatus } from '../components/RealtimeStatus'
import { useCallback, useState } from 'react'
import { api } from '../services/api'
import { formatDate } from '../services/format'
import { useResource } from '../hooks/useResource'
import { PriorityBadge, StatusBadge } from '../components/Badge'
import { ErrorMessage, Loading } from '../components/Feedback'
import { PageHeading } from '../components/PageHeading'
import { ActivityPanels } from '../components/ActivityPanels'
import { StatusActions } from '../components/StatusActions'

export function WorkOrderDetail({ id, created = false }: { id: number; created?: boolean }) {
  const resource = useResource(useCallback((signal: AbortSignal) => api.get(id, signal), [id]))
  const [message, setMessage] = useState(created ? 'ODL creato correttamente.' : '')
  const [activityVersion, setActivityVersion] = useState(0)
  function refresh() { resource.reload(); setActivityVersion(v => v + 1) }
  const realtime = useRealtime(refresh, id)
  const order = resource.data
  return <>
    <a className="text-link back-link" href="#/odl">← Torna agli ODL</a>
    <PageHeading title="Dettaglio ODL" description={order?.code || 'Informazioni e attività dell’ordine di lavoro.'} refresh={refresh} />
    <RealtimeStatus status={realtime} />
    {message && <div className="notice notice-success" role="status">{message}</div>}
    {resource.loading && !order ? <Loading /> : resource.error ? <ErrorMessage message={resource.error} retry={refresh} /> : order && <>
      <section className="surface order-details"><div className="section-heading"><div><p className="eyebrow">ORDINE DI LAVORO</p><h2 className="detail-code">{order.code}</h2></div><div className="badges"><PriorityBadge value={order.priority} /><StatusBadge value={order.status} /></div></div>
        <dl className="detail-grid"><div><dt>Richiedente</dt><dd>{order.user_first_name} {order.user_last_name}</dd></div><div><dt>Telefono</dt><dd><a href={`tel:${order.user_phone}`}>{order.user_phone}</a></dd></div>{order.user_email && <div><dt>Email</dt><dd><a href={`mailto:${order.user_email}`}>{order.user_email}</a></dd></div>}<div><dt>Indirizzo del guasto</dt><dd>{order.fault_address}</dd></div><div><dt>Categoria</dt><dd>Categoria #{order.category_id}</dd></div><div><dt>Solleciti</dt><dd>{order.reminders_count}</dd></div><div><dt>Creato il</dt><dd><time dateTime={order.created_at}>{formatDate(order.created_at, true)}</time></dd></div><div><dt>Ultimo aggiornamento</dt><dd><time dateTime={order.updated_at}>{formatDate(order.updated_at, true)}</time></dd></div></dl>
        <div className="description"><h3>Descrizione del guasto</h3><p>{order.description}</p></div>
      </section>
      <StatusActions key={`${order.id}-${order.status}`} order={order} onChanged={text => { setMessage(text); refresh() }} />
      <ActivityPanels key={id} id={id} refreshVersion={activityVersion} />
    </>}
  </>
}
