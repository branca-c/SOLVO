import { useState, type FormEvent } from 'react'
import { setDemoAccessKey } from '../services/demoAccess'

export function DemoAccessGate({ message, onAccepted }: { message?: string; onAccepted: () => void }) {
  const [key, setKey] = useState('')
  const [error, setError] = useState('')
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!key.trim()) {
      setError('Inserisci la chiave di accesso alla demo.')
      return
    }
    setDemoAccessKey(key)
    onAccepted()
  }
  return <main id="main-content" tabIndex={-1} className="demo-access-page">
    <section className="surface demo-access-card">
      <p className="eyebrow">SOLVO · DEMO</p>
      <h1>Accedi alla demo</h1>
      <p>Inserisci la chiave demo ricevuta. È conservata solo per questa sessione del browser.</p>
      {(message || error) && <p className="notice notice-error" role="alert">{message || error}</p>}
      <form onSubmit={submit}><label>Chiave di accesso<input type="password" autoFocus value={key} onChange={event => { setKey(event.target.value); setError('') }} autoComplete="off" /></label><button className="button button-primary" type="submit">Entra nella demo</button></form>
    </section>
  </main>
}
