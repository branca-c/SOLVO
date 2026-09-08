import type { ReactNode } from 'react'
import { Icon } from './Icon'
export function Layout({ title, section, children }: { title: string; section: 'dashboard' | 'odl' | 'tecnici'; children: ReactNode }) {
  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>Vai al contenuto</a>
    <aside className="sidebar">
      <a className="brand" href="#/" aria-label="SOLVO — Dashboard">SOL<span>V</span>O<i aria-hidden="true">✦</i></a>
      <p className="sidebar-caption">CENTRO DI CONTROLLO</p>
      <nav aria-label="Navigazione principale">
        <a href="#/" className={section === 'dashboard' ? 'nav-link active' : 'nav-link'} aria-current={section === 'dashboard' ? 'page' : undefined}><Icon name="dashboard" />Dashboard</a>
        <a href="#/odl" className={section === 'odl' ? 'nav-link active' : 'nav-link'} aria-current={section === 'odl' ? 'page' : undefined}><Icon name="orders" />ODL</a>
        <a href="#/tecnici" className={section === 'tecnici' ? 'nav-link active' : 'nav-link'} aria-current={section === 'tecnici' ? 'page' : undefined}><Icon name="users" />Tecnici</a>
        <button className="nav-link" disabled title="Sezione non disponibile"><Icon name="settings" />Impostazioni</button>
      </nav>
      <div className="sidebar-bottom"><span className="avatar operator-avatar">OP</span><div><strong>Operatore</strong><small>Area operativa</small></div></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="breadcrumb">Centro di controllo <span>/</span> <strong>{title}</strong></div><div className="operator"><span className="avatar">OP</span><div><strong>Operatore</strong><small>Postazione locale</small></div></div></header>
      <main id="main-content" tabIndex={-1}>{children}</main>
      <footer className="page-footer"><span>SOLVO · Gestione manutenzioni</span><span>Ogni intervento, sotto controllo.</span></footer>
    </div>
  </div>
}
