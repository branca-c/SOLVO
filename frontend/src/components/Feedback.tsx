import { Icon } from './Icon'
export function Loading({ text = 'Caricamento ODL…' }: { text?: string }) {
  return <div className="loading" role="status"><span className="spinner" />{text}</div>
}
export function ErrorMessage({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="notice notice-error" role="alert"><Icon name="urgent" /><div><strong>Qualcosa non ha funzionato</strong><p>{message}</p>{retry && <button className="button button-secondary" onClick={retry}>Riprova</button>}</div></div>
}
export function Empty({ title, text }: { title: string; text: string }) {
  return <div className="empty"><span className="empty-icon"><Icon name="orders" /></span><h3>{title}</h3><p>{text}</p></div>
}
