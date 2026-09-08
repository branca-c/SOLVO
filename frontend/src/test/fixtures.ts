import type { WorkOrder } from '../types/workOrder'
export const order: WorkOrder = {
  id: 1, code: 'SOLVO-20260908-A1B2C3D4E5F60708', created_at: '2026-09-08T08:00:00Z', updated_at: '2026-09-08T08:00:00Z',
  user_first_name: 'Ada', user_last_name: 'Rossi', user_phone: '+390123456789', user_email: 'ada@example.com',
  fault_address: 'Via Roma 12, Milano', category_id: 2, priority: 'URGENTE', status: 'APERTO',
  description: 'Perdita dal rubinetto del bagno al primo piano.', reminders_count: 1,
}
