import { useSyncExternalStore } from 'react'
function subscribe(callback: () => void) {
  window.addEventListener('hashchange', callback)
  return () => window.removeEventListener('hashchange', callback)
}
export function useRoute() {
  return useSyncExternalStore(subscribe, () => window.location.pathname.startsWith('/tecnico/assegnazione/') ? window.location.pathname : window.location.hash.slice(1) || '/', () => '/')
}
export function navigate(path: string) { window.location.hash = path }
