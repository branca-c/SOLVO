import { statusLabels, type Priority, type WorkOrderStatus } from '../types/workOrder'
export function PriorityBadge({ value }: { value: Priority }) {
  return <span className={`badge priority priority-${value.toLowerCase()}`}><span className="priority-dot" />{value}</span>
}
export function StatusBadge({ value }: { value: WorkOrderStatus }) {
  return <span className={`badge status-${value.toLowerCase()}`}>{statusLabels[value].toUpperCase()}</span>
}
