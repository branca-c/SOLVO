import { Icon } from './Icon'
export function PageHeading({ title, description, create = true, refresh }: { title: string; description: string; create?: boolean; refresh?: () => void }) {
  return <div className="page-heading"><div><p className="eyebrow">SOLVO / OPERATIVITÀ</p><h1>{title}</h1><p>{description}</p></div><div className="heading-actions">{refresh && <button className="button button-secondary" onClick={refresh}><Icon name="refresh" />Aggiorna</button>}{create && <a className="button button-primary" href="#/odl/nuovo"><Icon name="plus" />Nuovo ODL</a>}</div></div>
}
