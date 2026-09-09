// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WorkOrderDetail } from '../pages/WorkOrderDetail'
import { api } from '../services/api'
import { clearCategoriesCache } from '../hooks/useCategories'
import type { Assignment } from '../types/workOrder'
import { order } from './fixtures'

const pending: Assignment = {
  id: 12, work_order_id: 1, technician_id: 7, status: 'PENDING', attempt_number: 1,
  sent_at: order.created_at, responded_at: null, rejection_notes: null,
  technician: { id: 7, first_name: 'Demo', last_name: 'Uno', category_id: 2, phone: '123', email: null, escalation_order: 1, is_team_leader: false },
}
const next: Assignment = { ...pending, id: 13, technician_id: 8, attempt_number: 2, technician: { ...pending.technician, id: 8, last_name: 'Due', escalation_order: 2 } }
beforeEach(() => {
  vi.stubEnv('VITE_DEMO_USER_ID', '42')
  clearCategoriesCache()
  vi.spyOn(api, 'categories').mockResolvedValue([{ id: 2, name: 'Idraulico', description: null }])
  vi.spyOn(api, 'get').mockResolvedValue(order)
  vi.spyOn(api, 'history').mockResolvedValue([])
  vi.spyOn(api, 'reminders').mockResolvedValue([])
  vi.spyOn(api, 'assignments').mockResolvedValue([])
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllEnvs() })

it('starts once, refreshes history and shows the pending technician without a WebSocket event', async () => {
  let finish!: (value: Assignment) => void
  const start = vi.spyOn(api, 'startAssignment').mockImplementation(() => new Promise(resolve => { finish = resolve }))
  render(<WorkOrderDetail id={1} />)
  const button = await screen.findByRole('button', { name: 'Assegna tecnico' })
  await userEvent.click(button)
  expect((button as HTMLButtonElement).disabled).toBe(true)
  await userEvent.click(button)
  expect(start).toHaveBeenCalledTimes(1)
  expect(start).toHaveBeenCalledWith(1)
  vi.mocked(api.assignments).mockResolvedValue([pending])
  finish(pending)
  await screen.findByText('Demo Uno')
  expect(screen.getByText('PENDING')).toBeTruthy()
  expect(screen.getByText('Assegnazione avviata.')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Assegna tecnico' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Invia Telegram' })).toBeTruthy()
  await waitFor(() => expect(api.history).toHaveBeenCalledTimes(2))
})

it.each(['no-response', 'escalation'])('advances pending via %s and displays its successor', async action => {
  vi.mocked(api.assignments).mockResolvedValue([pending])
  const successor = action === 'escalation' ? { ...next, technician: { ...next.technician, is_team_leader: true } } : next
  const mutation = vi.spyOn(api, action === 'escalation' ? 'escalateTeamLeader' : 'noResponse').mockImplementation(async () => {
    vi.mocked(api.assignments).mockResolvedValue([{ ...pending, status: action === 'escalation' ? 'ESCALATED' : 'NO_RESPONSE' }, successor])
    return action === 'escalation' ? successor : { ...pending, status: 'NO_RESPONSE' }
  })
  render(<WorkOrderDetail id={1} />)
  await screen.findByText('Demo Uno')
  expect(screen.queryByRole('button', { name: 'Assegna tecnico' })).toBeNull()
  await userEvent.click(screen.getByRole('button', { name: action === 'escalation' ? 'Escala al caposquadra' : 'Nessuna risposta' }))
  await screen.findByText('Demo Due')
  expect(mutation).toHaveBeenCalledWith(action === 'escalation' ? 1 : 12)
  expect(screen.getAllByRole('button', { name: 'Invia Telegram' })).toHaveLength(1)
  await waitFor(() => expect(api.history).toHaveBeenCalledTimes(2))
  expect(screen.queryByRole('button', { name: 'Accetta' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Rifiuta' })).toBeNull()
})

it('adds a reminder with the configured user and refreshes list, count and history', async () => {
  const add = vi.spyOn(api, 'addReminder').mockImplementation(async () => {
    const reminder = { id: 22, work_order_id: 1, created_by: 42, created_at: order.created_at }
    vi.mocked(api.reminders).mockResolvedValue([reminder])
    vi.mocked(api.get).mockResolvedValue({ ...order, reminders_count: 2 })
    return reminder
  })
  render(<WorkOrderDetail id={1} />)
  await screen.findByText('Nessun sollecito ricevuto.')
  await userEvent.click(screen.getByRole('button', { name: 'Aggiungi sollecito' }))
  await screen.findByText('Sollecito #22')
  expect(add).toHaveBeenCalledWith(1, 42)
  expect(screen.getByText('Sollecito aggiunto.')).toBeTruthy()
  await waitFor(() => expect(screen.getByText('Solleciti', { selector: 'dt' }).nextElementSibling?.textContent).toBe('2'))
  expect(api.history).toHaveBeenCalledTimes(2)
})

it.each(['', '0', '-1', '1.5', 'NaN', '9007199254740992'])('disables reminders with invalid/missing demo identity: %s', async value => {
  vi.stubEnv('VITE_DEMO_USER_ID', value)
  render(<WorkOrderDetail id={1} />)
  await screen.findByText('Solleciti non disponibili: utente demo non configurato.')
  expect((screen.getByRole('button', { name: 'Aggiungi sollecito' }) as HTMLButtonElement).disabled).toBe(true)
})

it.each(['CHIUSO', 'ANNULLATO'] as const)('hides assignment mutations on %s even with a pending attempt', async status => {
  vi.mocked(api.get).mockResolvedValue({ ...order, status })
  vi.mocked(api.assignments).mockResolvedValue([pending])
  render(<WorkOrderDetail id={1} />)
  await screen.findByText('Demo Uno')
  const region = screen.getByRole('region', { name: 'Assegnazioni' })
  expect(within(region).queryByRole('button')).toBeNull()
})

it('shows accepted technician and does not offer an invalid routing restart', async () => {
  vi.mocked(api.assignments).mockResolvedValue([{ ...pending, status: 'ACCEPTED' }])
  render(<WorkOrderDetail id={1} />)
  await screen.findByText('ACCEPTED')
  expect(screen.getByText('Demo Uno')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Assegna tecnico' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Invia Telegram' })).toBeNull()
})

it('shows routing errors without success or retrying the mutation', async () => {
  vi.mocked(api.assignments).mockResolvedValue([pending])
  const advance = vi.spyOn(api, 'noResponse').mockRejectedValue(new Error('Nessun tecnico successivo'))
  render(<WorkOrderDetail id={1} />)
  await userEvent.click(await screen.findByRole('button', { name: 'Nessuna risposta' }))
  await screen.findByText('Nessun tecnico successivo')
  expect(screen.queryByText('Nessuna risposta registrata. Assegnazione avanzata.')).toBeNull()
  expect(advance).toHaveBeenCalledTimes(1)
  expect(screen.getByText('PENDING')).toBeTruthy()
})

it('uses existing POST contracts and serializes reminder attribution', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }))
  try {
    await api.startAssignment(5)
    await api.noResponse(12)
    await api.escalateTeamLeader(5)
    await api.addReminder(5, 42)
    expect(fetch).toHaveBeenNthCalledWith(1, '/api/work-orders/5/assignments/start', expect.objectContaining({ method: 'POST' }))
    expect(fetch).toHaveBeenNthCalledWith(2, '/api/assignments/12/no-response', expect.objectContaining({ method: 'POST' }))
    expect(fetch).toHaveBeenNthCalledWith(3, '/api/work-orders/5/assignments/escalate-team-leader', expect.objectContaining({ method: 'POST' }))
    expect(fetch).toHaveBeenNthCalledWith(4, '/api/work-orders/5/reminders', expect.objectContaining({ method: 'POST', body: '{"created_by":42}' }))
  } finally { vi.unstubAllGlobals() }
})
