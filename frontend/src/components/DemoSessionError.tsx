export function DemoSessionError({ busy, onRetry }: { busy: boolean; onRetry: () => void }) {
  return <main id="main-content" tabIndex={-1} className="demo-access-page">
    <section className="surface demo-access-card">
      <p className="eyebrow">SOLVO · DEMO</p>
      <h1>Impossibile avviare la demo</h1>
      <p>Non è stato possibile preparare la sessione di prova. Potrebbe trattarsi di un problema temporaneo.</p>
      <button className="button button-primary" type="button" disabled={busy} onClick={onRetry}>
        {busy ? 'Verifica…' : 'Riprova'}
      </button>
    </section>
  </main>
}
