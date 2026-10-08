export function DemoInUse({ retryAfterSeconds, onRetry, busy }: {
  retryAfterSeconds?: number; onRetry: () => void; busy: boolean
}) {
  const minutes = retryAfterSeconds ? Math.max(1, Math.ceil(retryAfterSeconds / 60)) : undefined
  return <main id="main-content" tabIndex={-1} className="demo-access-page">
    <section className="surface demo-access-card">
      <p className="eyebrow">SOLVO · DEMO</p>
      <h1>Demo temporaneamente in uso</h1>
      <p>Un altro visitatore sta completando una sessione di prova di SOLVO. Per evitare sovrapposizioni nei dati e nelle notifiche, la demo consente una sessione alla volta. La disponibilità viene ripristinata automaticamente al termine della sessione.</p>
      {minutes && <p><strong>Disponibile tra circa {minutes} min.</strong></p>}
      <button className="button button-primary" type="button" disabled={busy} onClick={onRetry}>
        {busy ? 'Verifica…' : 'Riprova ora'}
      </button>
    </section>
  </main>
}
