import type { FormEvent } from 'react'
import { ErrorMessage } from './Feedback'

export function AITextIntake({ text, onTextChange, onAnalyze, busy, error }: {
  text: string
  onTextChange: (text: string) => void
  onAnalyze: (event: FormEvent<HTMLFormElement>) => void
  busy: boolean
  error: string
}) {
  return <section className="surface ai-intake" aria-labelledby="ai-intake-heading">
    <div className="section-heading">
      <div><h2 id="ai-intake-heading"><span className="ai-spark" aria-hidden="true">✦</span> Dal testo alla bozza</h2>
        <p>Descrivi il guasto. Potrai correggere e completare ogni campo prima di creare l’ODL.</p></div>
      <span className="form-step">SOLVO AI</span>
    </div>
    <form onSubmit={onAnalyze} className="ai-intake-form" aria-busy={busy}>
      <label htmlFor="ai-source-text">Descrizione libera del guasto</label>
      <textarea id="ai-source-text" value={text} onChange={e => onTextChange(e.target.value)}
        required maxLength={10000} rows={5} disabled={busy} aria-describedby="ai-source-help"
        placeholder="Mi chiamo Ada Rossi. Telefono: 3331234567; Indirizzo: Via Roma 12; C’è una perdita dal tubo del bagno." />
      <p id="ai-source-help">Indica, se disponibili, nome, contatti e indirizzo. L’analisi prepara una bozza: nessun ODL viene creato.</p>
      {error && <ErrorMessage message={error} />}
      <div className="ai-intake-actions"><span role="status">{busy ? 'Analisi del testo in corso…' : `${text.length}/10000 caratteri`}</span>
        <button type="submit" className="button button-primary" disabled={busy || !text.trim()}>
          <span aria-hidden="true">✦</span>{busy ? 'Analisi in corso…' : 'Analizza con AI'}
        </button>
      </div>
    </form>
  </section>
}
