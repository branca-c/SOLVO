import { useCallback, useState } from 'react'
import { api } from '../services/api'
import { newestFirst } from '../services/format'
import { useResource } from '../hooks/useResource'
import { priorities, statuses, statusLabels, type Priority, type WorkOrderStatus } from '../types/workOrder'
import { PageHeading } from '../components/PageHeading'
import { WorkOrderTable } from '../components/WorkOrderTable'
import { ErrorMessage, Loading } from '../components/Feedback'
export function WorkOrders() {
  const [status, setStatus] = useState<WorkOrderStatus | ''>('')
  const [priority, setPriority] = useState<Priority | ''>('')
  const resource = useResource(useCallback((signal: AbortSignal) => api.list({ status, priority }, signal), [status, priority]))
  return <>
    <PageHeading title="Ordini di lavoro" description="Consulta le richieste, individua le priorità e segui ogni intervento." refresh={resource.reload} />
    <section className="surface">
      <div className="filters"><label><span id="filter-status-label">Stato</span><select aria-labelledby="filter-status-label" value={status} onChange={e => setStatus(e.target.value as WorkOrderStatus | '')}><option value="">Tutti gli stati</option>{statuses.map(s => <option key={s} value={s}>{statusLabels[s]}</option>)}</select></label><label><span id="filter-priority-label">Priorità</span><select aria-labelledby="filter-priority-label" value={priority} onChange={e => setPriority(e.target.value as Priority | '')}><option value="">Tutte le priorità</option>{priorities.map(p => <option key={p}>{p}</option>)}</select></label><button className="button button-quiet" disabled={!status && !priority} onClick={() => { setStatus(''); setPriority('') }}>Reimposta filtri</button><span className="result-count" role="status">{resource.data ? `${resource.data.length} ODL` : ''}</span></div>
      {resource.loading ? <Loading /> : resource.error ? <ErrorMessage message={resource.error} retry={resource.reload} /> : <WorkOrderTable full orders={newestFirst(resource.data ?? [])} />}
    </section>
  </>
}
