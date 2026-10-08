import { useState } from 'react'
import { api, messageFor, type DemoSessionStatus } from '../services/api'

export function DemoSessionPanel({ status, onStatus, onReleased }: {
  status: DemoSessionStatus; onStatus: (status: DemoSessionStatus) => void; onReleased: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  if (!status.enabled) return null

  async function connectTelegram() {
    setBusy(true); setMessage('')
    try {
      const result = await api.demoSessionTelegramLink()
      window.open(result.url, '_blank', 'noopener,noreferrer')
      setMessage('Completa il collegamento in Telegram, poi aggiorna lo stato.')
    } catch (error) { setMessage(messageFor(error)) }
    finally { setBusy(false) }
  }
  async function refresh() {
    setBusy(true); setMessage('')
    try { onStatus(await api.demoSessionStatus()) }
    catch (error) { setMessage(messageFor(error)) }
    finally { setBusy(false) }
  }
  async function unlink() {
    setBusy(true); setMessage('')
    try { await api.unlinkDemoSessionTelegram(); onStatus({ ...status, telegram_linked: false }) }
    catch (error) { setMessage(messageFor(error)) }
    finally { setBusy(false) }
  }
  async function end() {
    if (!window.confirm('Terminare la sessione demo e cancellare gli ODL creati?')) return
    setBusy(true); setMessage('')
    try { await api.releaseDemoSession(); onReleased() }
    catch (error) { setMessage(messageFor(error)); setBusy(false) }
  }

  return <section className="surface demo-session-panel" aria-labelledby="demo-session-heading">
    <div><h2 id="demo-session-heading">Telegram demo</h2>
      <p>Stato: <strong>{status.telegram_linked ? 'Collegato' : 'Non collegato'}</strong></p>
      {message && <p role="status">{message}</p>}
    </div>
    <div className="heading-actions">
      {status.telegram_linked
        ? <button className="button button-secondary" disabled={busy} onClick={unlink}>Scollega Telegram</button>
        : <button className="button button-secondary" disabled={busy} onClick={connectTelegram}>Collega il mio Telegram</button>}
      <button className="button button-secondary" disabled={busy} onClick={refresh}>Aggiorna stato</button>
      <button className="button button-secondary" disabled={busy} onClick={end}>Termina sessione demo</button>
    </div>
  </section>
}
