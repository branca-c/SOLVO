// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'
import { Dashboard } from '../pages/Dashboard'
import { WorkOrders } from '../pages/WorkOrders'
import { WorkOrderDetail } from '../pages/WorkOrderDetail'
import { CreateWorkOrder } from '../pages/CreateWorkOrder'
import { api } from '../services/api'
import { order } from './fixtures'
beforeEach(() => {
  window.location.hash = '/'
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  vi.spyOn(api, 'list').mockResolvedValue([order])
  vi.spyOn(api, 'get').mockResolvedValue(order)
  vi.spyOn(api, 'history').mockResolvedValue([{ id: 1, work_order_id: 1, event_type: 'CREATED', description: 'ODL creata: APERTO', created_at: order.created_at }])
  vi.spyOn(api, 'reminders').mockResolvedValue([{ id: 1, work_order_id: 1, created_by: 4, created_at: order.created_at }])
  vi.spyOn(api, 'assignments').mockResolvedValue([])
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })
it('renders dashboard counts and navigates to an ODL from its link', async () => {
  render(<App />)
  expect(await screen.findByRole('link', { name: order.code })).toBeTruthy()
  expect(within(screen.getByRole('region', { name: 'Totale ODL' })).getByText('1')).toBeTruthy()
  await userEvent.click(screen.getByRole('link', { name: order.code }))
  expect(await screen.findByRole('heading', { name: 'Dettaglio ODL' })).toBeTruthy()
  expect(await screen.findByText(order.description)).toBeTruthy()
})
it('applies server filters and resets them', async () => {
  render(<WorkOrders />)
  await screen.findByText(order.code)
  await userEvent.selectOptions(screen.getByLabelText('Stato'), 'IN_CORSO')
  await userEvent.selectOptions(screen.getByLabelText('Priorità'), 'ALTA')
  await waitFor(() => expect(api.list).toHaveBeenLastCalledWith({ status: 'IN_CORSO', priority: 'ALTA' }, expect.any(AbortSignal)))
  await userEvent.click(screen.getByRole('button', { name: 'Reimposta filtri' }))
  await waitFor(() => expect(api.list).toHaveBeenLastCalledWith({ status: '', priority: '' }, expect.any(AbortSignal)))
})
it('shows loading, recoverable errors, and an empty state', async () => {
  vi.mocked(api.list).mockRejectedValueOnce(new Error('Servizio non disponibile')).mockResolvedValueOnce([])
  render(<Dashboard />)
  expect(screen.getByText('Caricamento ODL…').textContent).toContain('Caricamento')
  expect(await screen.findByRole('alert')).toBeTruthy()
  await userEvent.click(screen.getByRole('button', { name: 'Riprova' }))
  expect(await screen.findByText('Nessun ODL da mostrare')).toBeTruthy()
})
it('creates from a labeled form and navigates only after success', async () => {
  const create = vi.spyOn(api, 'create').mockResolvedValue(order)
  const onCreated = vi.fn()
  render(<CreateWorkOrder onCreated={onCreated} />)
  await userEvent.type(screen.getByLabelText('Nome *'), 'Ada')
  await userEvent.type(screen.getByLabelText('Cognome *'), 'Rossi')
  await userEvent.type(screen.getByLabelText('Telefono *'), '123456')
  await userEvent.type(screen.getByLabelText('Indirizzo del guasto *'), 'Via Roma 12')
  await userEvent.type(screen.getByLabelText('ID categoria *'), '2')
  await userEvent.type(screen.getByLabelText('Descrizione del guasto *'), 'Perdita acqua')
  await userEvent.click(screen.getByRole('button', { name: 'Crea ODL' }))
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(1))
  expect(create).toHaveBeenCalledWith({ user_first_name: 'Ada', user_last_name: 'Rossi', user_phone: '123456', user_email: null, fault_address: 'Via Roma 12', category_id: 2, description: 'Perdita acqua', priority: 'MEDIA' })
  expect(window.location.hash).toBe('#/odl/1')
})
it('shows creation success and all related sections; updates status and history', async () => {
  vi.spyOn(api, 'status').mockImplementation(async () => {
    vi.mocked(api.get).mockResolvedValue({ ...order, status: 'IN_CORSO' })
    return { ...order, status: 'IN_CORSO' }
  })
  render(<WorkOrderDetail id={1} created />)
  expect(screen.getByText('ODL creato correttamente.').getAttribute('role')).toBe('status')
  await screen.findByText('ODL creata: APERTO')
  expect(await screen.findByText('Sollecito #1')).toBeTruthy()
  expect(await screen.findByText('Nessun tecnico ancora assegnato.')).toBeTruthy()
  const statusSelect = screen.getByLabelText('Nuovo stato')
  expect(within(statusSelect).queryByRole('option', { name: 'Chiuso' })).toBeNull()
  await userEvent.click(screen.getByRole('button', { name: 'Applica stato' }))
  await waitFor(() => expect(api.status).toHaveBeenCalledWith(1, 'IN_CORSO'))
  expect(await screen.findByText('Stato aggiornato: In corso.')).toBeTruthy()
  await waitFor(() => expect(api.history).toHaveBeenCalledTimes(2))
})
it('keeps ODL data visible when a related section fails', async () => {
  vi.mocked(api.history).mockRejectedValue(new Error('Storico non disponibile'))
  render(<WorkOrderDetail id={1} />)
  expect(await screen.findByText(order.description)).toBeTruthy()
  expect(await screen.findByText('Storico non disponibile')).toBeTruthy()
  expect(await screen.findByText('Sollecito #1')).toBeTruthy()
})
it('shows a status conflict inline without claiming success', async () => {
  vi.spyOn(api, 'status').mockRejectedValue(new Error('Transizione non consentita'))
  render(<WorkOrderDetail id={1} />)
  await screen.findByLabelText('Nuovo stato')
  await userEvent.click(screen.getByRole('button', { name: 'Applica stato' }))
  expect(await screen.findByText('Transizione non consentita')).toBeTruthy()
  expect(screen.queryByText(/Stato aggiornato:/)).toBeNull()
})
it('offers no transitions for terminal ODLs', async () => {
  vi.mocked(api.get).mockResolvedValue({ ...order, status: 'CHIUSO' })
  render(<WorkOrderDetail id={1} />)
  await screen.findByText(order.description)
  expect(screen.queryByRole('button', { name: 'Applica stato' })).toBeNull()
  expect(screen.getByText(/Questo ODL è concluso/)).toBeTruthy()
})
