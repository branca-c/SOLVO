export const priorities = ['PROGRAMMABILE', 'BASSA', 'MEDIA', 'ALTA', 'URGENTE'] as const
export const statuses = ['APERTO', 'IN_CORSO', 'EVASO', 'CHIUSO', 'ANNULLATO'] as const
export type Priority = typeof priorities[number]
export type WorkOrderStatus = typeof statuses[number]
export interface WorkOrderInput {
  user_first_name: string
  user_last_name: string
  user_phone: string
  user_email: string | null
  fault_address: string
  category_id: number
  priority: Priority
  description: string
}
export interface WorkOrder extends WorkOrderInput {
  id: number
  code: string
  created_at: string
  updated_at: string
  status: WorkOrderStatus
  reminders_count: number
}
export interface Reminder {
  id: number
  work_order_id: number
  created_at: string
  created_by: number
}
export interface HistoryEntry {
  id: number
  work_order_id: number
  event_type: string
  description: string
  created_at: string
}
export interface Assignment {
  id: number
  work_order_id: number
  technician_id: number
  status: 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'NO_RESPONSE' | 'ESCALATED'
  sent_at: string
  responded_at: string | null
  rejection_notes: string | null
  attempt_number: number
  technician: {
    id: number
    first_name: string
    last_name: string
    phone: string
    email: string | null
    category_id: number
    escalation_order: number
    is_team_leader: boolean
  }
}
export const transitions: Record<WorkOrderStatus, readonly WorkOrderStatus[]> = {
  APERTO: ['IN_CORSO', 'ANNULLATO'],
  IN_CORSO: ['EVASO', 'ANNULLATO'],
  EVASO: ['CHIUSO', 'IN_CORSO'],
  CHIUSO: [],
  ANNULLATO: [],
}
export const statusLabels: Record<WorkOrderStatus, string> = {
  APERTO: 'Aperto', IN_CORSO: 'In corso', EVASO: 'Evaso', CHIUSO: 'Chiuso', ANNULLATO: 'Annullato',
}
export const assignmentLabels: Record<Assignment['status'], string> = {
  PENDING: 'In attesa', ACCEPTED: 'Accettata', REJECTED: 'Rifiutata',
  NO_RESPONSE: 'Nessuna risposta', ESCALATED: 'Escalation',
}


export interface WorkOrderDraft {
  user_first_name: string | null
  user_last_name: string | null
  user_phone: string | null
  user_email: string | null
  fault_address: string | null
  category_id: number | null
  category_name: string | null
  priority: Priority | null
  description: string
  warnings: string[]
}

export interface AudioWorkOrderDraft {
  transcript: string
  draft: WorkOrderDraft
}
