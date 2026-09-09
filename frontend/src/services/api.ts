import type { Category, Technician } from '../types/referenceData'
import type { Assignment, HistoryEntry, Reminder, WorkOrder, WorkOrderInput, WorkOrderStatus, Priority, WorkOrderDraft, AudioWorkOrderDraft, PublicAssignment, NotificationResult } from '../types/workOrder'

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}
const fieldLabels: Record<string, string> = {
  user_first_name: 'Nome', user_last_name: 'Cognome', user_phone: 'Telefono',
  user_email: 'Email', fault_address: 'Indirizzo', category_id: 'Categoria',
  priority: 'Priorità', description: 'Descrizione', status: 'Stato', text: 'Descrizione libera',
}
export function errorDetail(body: unknown): string | undefined {
  if (!body || typeof body !== 'object' || !('detail' in body)) return
  const detail = body.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const fields = detail.flatMap((item: unknown) => {
      if (!item || typeof item !== 'object' || !('loc' in item) || !Array.isArray(item.loc)) return []
      const field = String(item.loc.at(-1))
      return [fieldLabels[field] || 'Dati inseriti']
    })
    return fields.length ? `Controlla i campi: ${[...new Set(fields)].join(', ')}.` : 'Controlla i dati inseriti.'
  }
}
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    // Same-origin requests: Vite forwards /api to VITE_API_BASE_URL locally.
    response = await fetch(`/api${path}`, {
      ...options,
      headers: { Accept: 'application/json', ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}) },
    })
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error
    throw new ApiError('Connessione non riuscita. Verifica che il servizio sia raggiungibile e riprova.', 0)
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(errorDetail(body) || (response.status === 404
      ? 'ODL non trovato.' : 'Impossibile completare la richiesta. Riprova tra poco.'), response.status)
  }
  if (body === null) throw new ApiError('Il servizio ha restituito una risposta non valida.', response.status)
  return body as T
}
export function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : 'Si è verificato un errore. Riprova.'
}
export const api = {
  startAssignment: (id: number) => request<Assignment>(`/work-orders/${id}/assignments/start`, { method: 'POST' }),
  noResponse: (id: number) => request<Assignment>(`/assignments/${id}/no-response`, { method: 'POST' }),
  escalateTeamLeader: (id: number) => request<Assignment>(`/work-orders/${id}/assignments/escalate-team-leader`, { method: 'POST' }),
  addReminder: (id: number, createdBy: number) => request<Reminder>(`/work-orders/${id}/reminders`, { method: 'POST', body: JSON.stringify({ created_by: createdBy }) }),
  categories: () => request<Category[]>('/categories'),
  technicians: (categoryId?: number, signal?: AbortSignal) => request<Technician[]>(`/technicians${categoryId === undefined ? '' : `?category_id=${categoryId}`}`, { signal }),
  publicAssignment: (token: string, signal?: AbortSignal) => request<PublicAssignment>(`/public/assignments/${encodeURIComponent(token)}`, { signal, cache: 'no-store' }),
  publicAccept: (token: string) => request<PublicAssignment>(`/public/assignments/${encodeURIComponent(token)}/accept`, { method: 'POST' }),
  publicReject: (token: string, rejection_notes: string | null) => request<PublicAssignment>(`/public/assignments/${encodeURIComponent(token)}/reject`, { method: 'POST', body: JSON.stringify({ rejection_notes }) }),
  notifyAssignment: (id: number) => request<NotificationResult>(`/assignments/${id}/notify`, { method: 'POST' }),
  audioDraft: (audio: File, signal?: AbortSignal) => {
    const body = new FormData()
    body.append('audio', audio)
    return request<AudioWorkOrderDraft>('/ai/work-order-draft-audio', { method: 'POST', body, signal })
  },
  draft: (text: string, signal?: AbortSignal) => request<WorkOrderDraft>('/ai/work-order-draft', {
    method: 'POST', body: JSON.stringify({ text }), signal,
  }),
  list: (filters: { status?: WorkOrderStatus | ''; priority?: Priority | '' } = {}, signal?: AbortSignal) => {
    const query = new URLSearchParams()
    if (filters.status) query.set('status', filters.status)
    if (filters.priority) query.set('priority', filters.priority)
    return request<WorkOrder[]>(`/work-orders${query.size ? `?${query}` : ''}`, { signal })
  },
  get: (id: number, signal?: AbortSignal) => request<WorkOrder>(`/work-orders/${id}`, { signal }),
  create: (input: WorkOrderInput) => request<WorkOrder>('/work-orders', { method: 'POST', body: JSON.stringify(input) }),
  status: (id: number, status: WorkOrderStatus) => request<WorkOrder>(`/work-orders/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  reminders: (id: number, signal?: AbortSignal) => request<Reminder[]>(`/work-orders/${id}/reminders`, { signal }),
  history: (id: number, signal?: AbortSignal) => request<HistoryEntry[]>(`/work-orders/${id}/history`, { signal }),
  assignments: (id: number, signal?: AbortSignal) => request<Assignment[]>(`/work-orders/${id}/assignments`, { signal }),
}
