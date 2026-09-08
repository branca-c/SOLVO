import type { WorkOrder } from '../types/workOrder'
import { formatDate } from '../services/format'
import { navigate } from '../services/navigation'
import { PriorityBadge, StatusBadge } from './Badge'
import { Empty } from './Feedback'

export function WorkOrderTable({ orders, full = false }: { orders: WorkOrder[]; full?: boolean }) {
  if (!orders.length) return <Empty title="Nessun ODL da mostrare" text="Crea un nuovo ordine di lavoro oppure modifica i filtri." />
  return <div className="table-container"><table className={full ? 'odl-table full-table' : 'odl-table'}>
    <caption className="sr-only">Ordini di lavoro dal più recente</caption>
    <thead><tr><th scope="col">Codice</th><th scope="col">Data</th><th scope="col">Richiedente</th>{full && <th scope="col">Indirizzo</th>}<th scope="col">Categoria</th><th scope="col">Priorità</th><th scope="col">Stato</th>{full && <th scope="col">Solleciti</th>}</tr></thead>
    <tbody>{orders.map(order => <tr key={order.id} onClick={event => {
      if (!(event.target as HTMLElement).closest('a')) navigate(`/odl/${order.id}`)
    }}>
      <td data-label="Codice"><a className="order-link" href={`#/odl/${order.id}`}>{order.code}</a></td>
      <td data-label="Data"><time dateTime={order.created_at}>{formatDate(order.created_at)}</time></td>
      <td data-label="Richiedente"><span className="requester"><span className="avatar small" aria-hidden="true">{order.user_first_name[0]}{order.user_last_name[0]}</span><span>{order.user_first_name} {order.user_last_name}</span></span></td>
      {full && <td data-label="Indirizzo" className="address-cell">{order.fault_address}</td>}
      <td data-label="Categoria">Categoria #{order.category_id}</td>
      <td data-label="Priorità"><PriorityBadge value={order.priority} /></td>
      <td data-label="Stato"><StatusBadge value={order.status} /></td>
      {full && <td data-label="Solleciti"><span className="count">{order.reminders_count}</span></td>}
    </tr>)}</tbody>
  </table></div>
}
