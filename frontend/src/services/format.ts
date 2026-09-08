import type { WorkOrder } from '../types/workOrder'
export function formatDate(value: string, time = false): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Data non disponibile'
  return new Intl.DateTimeFormat('it-IT', { dateStyle: 'medium', ...(time ? { timeStyle: 'short' as const } : {}) }).format(date)
}
export function newestFirst(orders: WorkOrder[]): WorkOrder[] {
  return [...orders].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at) || b.id - a.id)
}
export function summarize(orders: WorkOrder[]) {
  return {
    total: orders.length,
    open: orders.filter(o => o.status === 'APERTO').length,
    ongoing: orders.filter(o => o.status === 'IN_CORSO').length,
    urgent: orders.filter(o => o.priority === 'URGENTE').length,
    complete: orders.filter(o => o.status === 'EVASO' || o.status === 'CHIUSO').length,
  }
}
