import { useCallback } from 'react'
import { api } from '../services/api'
import { newestFirst, summarize } from '../services/format'
import { useResource } from '../hooks/useResource'
import { Icon, type IconName } from '../components/Icon'
import { PageHeading } from '../components/PageHeading'
import { WorkOrderTable } from '../components/WorkOrderTable'
import { ErrorMessage, Loading } from '../components/Feedback'
export function Dashboard() {
  const resource = useResource(useCallback((signal: AbortSignal) => api.list({}, signal), []))
  const stats = resource.data ? summarize(resource.data) : undefined
  const cards: { label: string; value: number | undefined; icon: IconName; color: string; note: string }[] = [
    { label: 'Totale ODL', value: stats?.total, icon: 'orders', color: 'indigo', note: 'Tutti gli ordini di lavoro' },
    { label: 'Aperti', value: stats?.open, icon: 'clock', color: 'blue', note: 'Da prendere in carico' },
    { label: 'In corso', value: stats?.ongoing, icon: 'settings', color: 'aqua', note: 'Interventi in lavorazione' },
    { label: 'Urgenti', value: stats?.urgent, icon: 'urgent', color: 'red', note: 'Priorità URGENTE · tutti gli stati' },
    { label: 'Evasi / Chiusi', value: stats?.complete, icon: 'check', color: 'cyan', note: 'Interventi evasi o chiusi' },
  ]
  return <>
    <PageHeading title="La tua operatività, a colpo d’occhio." description="Una visione chiara degli ordini di lavoro e delle attività in corso." refresh={resource.reload} />
    <div className="summary-grid">{cards.map(card => <section className="summary-card" key={card.label} aria-label={card.label}><div className={`metric-icon ${card.color}`}><Icon name={card.icon} /></div><div><h2>{card.label}</h2><strong className="metric-value">{card.value ?? '—'}</strong></div><p>{card.note}</p></section>)}</div>
    <section className="surface"><div className="section-heading"><div><h2>ODL recenti</h2><p>Gli ultimi ordini di lavoro inseriti</p></div><a className="text-link" href="#/odl">Tutti gli ODL <Icon name="arrow" /></a></div>
      {resource.loading ? <Loading /> : resource.error ? <ErrorMessage message={resource.error} retry={resource.reload} /> : <WorkOrderTable orders={newestFirst(resource.data ?? []).slice(0, 8)} />}
      <div className="table-footer"><span>Fino a 8 ordini · Dal più recente</span><span>Dati aggiornati al caricamento</span></div>
    </section>
  </>
}
