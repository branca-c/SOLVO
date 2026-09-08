export type IconName = 'dashboard' | 'orders' | 'users' | 'settings' | 'plus' | 'arrow' | 'check' | 'clock' | 'urgent' | 'refresh'
const paths: Record<IconName, string> = {
  dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  orders: 'M8 4H5v17h14V4h-3 M8 3h8v4H8z M8 12h8 M8 16h5',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M13 4a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-3.87 M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8',
  settings: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z',
  plus: 'M12 5v14 M5 12h14', arrow: 'M5 12h14 M13 6l6 6-6 6',
  check: 'M8 12l3 3 5-6 M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20',
  clock: 'M12 7v5l3 2 M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20',
  urgent: 'M12 8v5 M12 17h.01 M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20',
  refresh: 'M20 7v5h-5 M4 17v-5h5 M6 7a7 7 0 0 1 12-2l2 3 M4 16l2 3a7 7 0 0 0 12-2',
}
export function Icon({ name }: { name: IconName }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
