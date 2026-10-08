import { useState, type ReactNode } from 'react'
import { Icon } from './Icon'
import { DemoSessionPanel } from './DemoSessionPanel'
import type { DemoSessionStatus } from '../services/api'
export function Layout({ title, section, children, demoSession, onDemoSession, onDemoReleased }: {
  title: string; section: 'dashboard' | 'odl' | 'tecnici'; children: ReactNode
  demoSession?: DemoSessionStatus; onDemoSession?: (status: DemoSessionStatus) => void; onDemoReleased?: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = () => setMenuOpen(false)
  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>Vai al contenuto</a>
    <aside className={menuOpen ? 'sidebar sidebar-open' : 'sidebar'}>
      <a className="brand" href="#/" aria-label="SOLVO — Dashboard" onClick={closeMenu}>SOL<span>V</span>O<i aria-hidden="true">✦</i></a>
      <p className="sidebar-caption">CENTRO DI CONTROLLO</p>
      <nav id="primary-navigation" aria-label="Navigazione principale">
        <a href="#/" onClick={closeMenu} className={section === 'dashboard' ? 'nav-link active' : 'nav-link'} aria-current={section === 'dashboard' ? 'page' : undefined}><Icon name="dashboard" />Dashboard</a>
        <a href="#/odl" onClick={closeMenu} className={section === 'odl' ? 'nav-link active' : 'nav-link'} aria-current={section === 'odl' ? 'page' : undefined}><Icon name="orders" />ODL</a>
        <a href="#/tecnici" onClick={closeMenu} className={section === 'tecnici' ? 'nav-link active' : 'nav-link'} aria-current={section === 'tecnici' ? 'page' : undefined}><Icon name="users" />Tecnici</a>
        <button className="nav-link" disabled title="Sezione non disponibile"><Icon name="settings" />Impostazioni</button>
      </nav>
      <div className="sidebar-bottom"><span className="avatar operator-avatar">OP</span><div><strong>Operatore</strong><small>Area operativa</small></div></div>
    </aside>
    {menuOpen && <button type="button" className="mobile-nav-scrim" aria-label="Chiudi menu di navigazione" onClick={closeMenu} />}
    <div className="workspace">
      <header className="topbar"><button type="button" className="mobile-menu-toggle" aria-controls="primary-navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(open => !open)}><Icon name={menuOpen ? 'close' : 'menu'} /><span>{menuOpen ? 'Chiudi' : 'Menu'}</span></button><div className="breadcrumb">Centro di controllo <span>/</span> <strong>{title}</strong></div><div className="operator"><span className="avatar">OP</span><div><strong>Operatore</strong><small>Postazione locale</small></div></div></header>
      <main id="main-content" tabIndex={-1}>
        {demoSession && onDemoSession && onDemoReleased && <DemoSessionPanel status={demoSession} onStatus={onDemoSession} onReleased={onDemoReleased} />}
        {children}
      </main>
      <footer className="page-footer"><span>SOLVO · Gestione manutenzioni</span><span>Ogni intervento, sotto controllo.</span></footer>
    </div>
  </div>
}
