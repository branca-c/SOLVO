import { Technicians } from './pages/Technicians'
import { useEffect, useRef, useState } from 'react'
import { DemoAccessGate } from './components/DemoAccessGate'
import { clearDemoAccessKey, demoAccessRejectedEvent, getDemoAccessKey } from './services/demoAccess'
import { DemoInUse } from './components/DemoInUse'
import { DemoSessionError } from './components/DemoSessionError'
import { api, ApiError, type DemoSessionAcquisition, type DemoSessionStatus } from './services/api'
import { clearDemoSessionToken, demoSessionRejectedEvent, getDemoSessionToken, setDemoSessionToken } from './services/demoSession'
import { TechnicianAssignment } from './pages/TechnicianAssignment'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { WorkOrders } from './pages/WorkOrders'
import { WorkOrderDetail } from './pages/WorkOrderDetail'
import { CreateWorkOrder } from './pages/CreateWorkOrder'
import { useRoute } from './services/navigation'

function isDemoSessionStatus(value: unknown): value is DemoSessionStatus {
  return Boolean(value) && typeof value === 'object'
    && typeof (value as DemoSessionStatus).enabled === 'boolean'
    && ((value as DemoSessionStatus).expires_at === null || typeof (value as DemoSessionStatus).expires_at === 'string')
    && typeof (value as DemoSessionStatus).telegram_linked === 'boolean'
}

function isDemoSessionAcquisition(value: unknown): value is DemoSessionAcquisition {
  return isDemoSessionStatus(value)
    && ('session_token' in value)
    && (value.session_token === null || typeof value.session_token === 'string')
}

function confirmsInvalidDemoSession(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

export default function App() {
  const route = useRoute()
  const [createdId, setCreatedId] = useState<number>()
  const [hasDemoAccess, setHasDemoAccess] = useState(() => Boolean(getDemoAccessKey()))
  const [accessMessage, setAccessMessage] = useState('')
  const [demoSession, setDemoSession] = useState<DemoSessionStatus>()
  const [occupied, setOccupied] = useState<{ retryAfterSeconds?: number }>()
  const [sessionError, setSessionError] = useState(false)
  const [sessionBusy, setSessionBusy] = useState(false)
  const acquiring = useRef(false)
  const activeSinceHeartbeat = useRef(false)
  const previousRoute = useRef(route)
  const detail = /^\/odl\/([1-9]\d*)$/.exec(route)
  const id = detail ? Number(detail[1]) : undefined
  const technician = /^\/tecnico\/assegnazione\/([^/]+)$/.exec(route)
  const title = technician ? 'Intervento tecnico' : route === '/tecnici' ? 'Tecnici' : route === '/' ? 'Dashboard' : route === '/odl/nuovo' ? 'Nuovo ODL' : id ? 'Dettaglio ODL' : 'ODL'
  useEffect(() => {
    document.title = `${title} · SOLVO`
    if (previousRoute.current !== route) {
      document.getElementById('main-content')?.focus()
      window.scrollTo(0, 0)
    }
    previousRoute.current = route
  }, [route, title])
  useEffect(() => {
    const rejected = () => { setHasDemoAccess(false); setAccessMessage('La chiave demo non è valida o non è più disponibile.') }
    window.addEventListener(demoAccessRejectedEvent, rejected)
    return () => window.removeEventListener(demoAccessRejectedEvent, rejected)
  }, [])
  async function acquireSession() {
    if (acquiring.current) return
    acquiring.current = true; setSessionBusy(true)
    try {
      const existing = getDemoSessionToken()
      if (existing) {
        try {
          const status = await api.heartbeatDemoSession()
          if (!isDemoSessionStatus(status)) throw new ApiError('Risposta sessione non valida.', 200)
          setDemoSession(status); setOccupied(undefined); return
        } catch (error) {
          if (!confirmsInvalidDemoSession(error)) {
            setSessionError(true); return
          }
          clearDemoSessionToken()
        }
      }
      const acquired = await api.acquireDemoSession()
      if (!isDemoSessionAcquisition(acquired)) throw new ApiError('Risposta sessione non valida.', 200)
      if (acquired.session_token) setDemoSessionToken(acquired.session_token)
      setDemoSession(acquired); setOccupied(undefined); setSessionError(false)
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const detail = error.body && typeof error.body === 'object' && 'detail' in error.body
          ? error.body.detail : undefined
        const retry = detail && typeof detail === 'object' && 'retry_after_seconds' in detail
          ? Number(detail.retry_after_seconds) : undefined
        setOccupied({ retryAfterSeconds: Number.isFinite(retry) ? retry : undefined }); setSessionError(false)
      } else {
        setSessionError(true)
      }
    } finally { acquiring.current = false; setSessionBusy(false) }
  }
  useEffect(() => {
    if (hasDemoAccess && !demoSession && !occupied && !sessionError) void acquireSession()
  }, [hasDemoAccess, demoSession, occupied, sessionError])
  useEffect(() => {
    const rejected = () => { setDemoSession(undefined); setSessionError(false) }
    window.addEventListener(demoSessionRejectedEvent, rejected)
    return () => window.removeEventListener(demoSessionRejectedEvent, rejected)
  }, [])
  useEffect(() => {
    if (!demoSession?.enabled) return
    const markActive = () => { activeSinceHeartbeat.current = true }
    window.addEventListener('pointerdown', markActive)
    window.addEventListener('keydown', markActive)
    const timer = window.setInterval(async () => {
      if (!activeSinceHeartbeat.current) return
      activeSinceHeartbeat.current = false
      try { setDemoSession(await api.heartbeatDemoSession()) } catch { /* rejection event handles expiry */ }
    }, 60_000)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('pointerdown', markActive)
      window.removeEventListener('keydown', markActive)
    }
  }, [demoSession?.enabled])
  function released() {
    clearDemoSessionToken(); clearDemoAccessKey(); setDemoSession(undefined)
    setOccupied(undefined); setSessionError(false); setHasDemoAccess(false); setAccessMessage('Sessione demo terminata correttamente.')
  }
  if (technician) return <TechnicianAssignment key={technician[1]} token={technician[1]} />
  if (!hasDemoAccess) return <DemoAccessGate message={accessMessage} onAccepted={() => { setAccessMessage(''); setSessionError(false); setHasDemoAccess(true) }} />
  if (occupied) return <DemoInUse retryAfterSeconds={occupied.retryAfterSeconds} busy={sessionBusy} onRetry={() => { setOccupied(undefined); void acquireSession() }} />
  if (sessionError) return <DemoSessionError busy={sessionBusy} onRetry={() => { setSessionError(false); void acquireSession() }} />
  if (!demoSession) return <main className="demo-access-page"><p role="status">Preparazione della demo…</p></main>
  return <Layout title={title} section={route === '/tecnici' ? 'tecnici' : route === '/' ? 'dashboard' : 'odl'} demoSession={demoSession} onDemoSession={setDemoSession} onDemoReleased={released}>
    {route === '/tecnici' ? <Technicians /> : route === '/' ? <Dashboard /> : route === '/odl' ? <WorkOrders /> : route === '/odl/nuovo' ? <CreateWorkOrder onCreated={setCreatedId} /> : id && Number.isSafeInteger(id) ? <WorkOrderDetail key={id} id={id} created={createdId === id} /> : <section className="surface empty"><h1>Pagina non trovata</h1><p>Il percorso richiesto non è disponibile.</p><a className="button button-primary" href="#/">Vai alla Dashboard</a></section>}
  </Layout>
}
