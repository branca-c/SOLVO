import { useEffect, useRef, useState } from 'react'
import { TechnicianAssignment } from './pages/TechnicianAssignment'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { WorkOrders } from './pages/WorkOrders'
import { WorkOrderDetail } from './pages/WorkOrderDetail'
import { CreateWorkOrder } from './pages/CreateWorkOrder'
import { useRoute } from './services/navigation'
export default function App() {
  const route = useRoute()
  const [createdId, setCreatedId] = useState<number>()
  const previousRoute = useRef(route)
  const detail = /^\/odl\/([1-9]\d*)$/.exec(route)
  const id = detail ? Number(detail[1]) : undefined
  const technician = /^\/tecnico\/assegnazione\/([^/]+)$/.exec(route)
  const title = technician ? 'Intervento tecnico' : route === '/' ? 'Dashboard' : route === '/odl/nuovo' ? 'Nuovo ODL' : id ? 'Dettaglio ODL' : 'ODL'
  useEffect(() => {
    document.title = `${title} · SOLVO`
    if (previousRoute.current !== route) {
      document.getElementById('main-content')?.focus()
      window.scrollTo(0, 0)
    }
    previousRoute.current = route
  }, [route, title])
  if (technician) return <TechnicianAssignment key={technician[1]} token={technician[1]} />
  return <Layout title={title} section={route === '/' ? 'dashboard' : 'odl'}>
    {route === '/' ? <Dashboard /> : route === '/odl' ? <WorkOrders /> : route === '/odl/nuovo' ? <CreateWorkOrder onCreated={setCreatedId} /> : id && Number.isSafeInteger(id) ? <WorkOrderDetail key={id} id={id} created={createdId === id} /> : <section className="surface empty"><h1>Pagina non trovata</h1><p>Il percorso richiesto non è disponibile.</p><a className="button button-primary" href="#/">Vai alla Dashboard</a></section>}
  </Layout>
}
