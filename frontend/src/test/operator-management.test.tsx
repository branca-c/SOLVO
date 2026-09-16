// @vitest-environment jsdom
import { beforeEach, afterEach, it, expect, vi } from 'vitest'
import { render, screen, waitFor, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Dashboard } from '../pages/Dashboard'
import { WorkOrders } from '../pages/WorkOrders'
import { WorkOrderDetail } from '../pages/WorkOrderDetail'
import { Technicians } from '../pages/Technicians'
import { api, ApiError } from '../services/api'
import { clearCategoriesCache } from '../hooks/useCategories'
import { order } from './fixtures'
vi.mock('../hooks/useRealtime', () => ({ useRealtime: () => 'Connesso' }))
beforeEach(() => {
  clearCategoriesCache()
  vi.stubEnv('VITE_DEMO_USER_ID', '4')
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  vi.spyOn(api, 'categories').mockResolvedValue([{ id: 2, name: 'Idraulico', description: null }])
  vi.spyOn(api, 'list').mockResolvedValue([order])
  vi.spyOn(api, 'get').mockResolvedValue(order)
  vi.spyOn(api, 'notes').mockResolvedValue([])
  vi.spyOn(api, 'history').mockResolvedValue([])
  vi.spyOn(api, 'reminders').mockResolvedValue([])
  vi.spyOn(api, 'assignments').mockResolvedValue([])
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllEnvs() })
for (const Page of [Dashboard, WorkOrders]) {
  it(`${Page.name}: edits values and refreshes; deletes only after confirmation`, async () => {
    vi.spyOn(api, 'update').mockImplementation(async (_id, data) => {
      const updated = { ...order, ...data }; vi.mocked(api.list).mockResolvedValue([updated]); return updated
    })
    const remove = vi.spyOn(api, 'delete').mockImplementation(async () => { vi.mocked(api.list).mockResolvedValue([]) })
    render(<Page />)
    await userEvent.click(await screen.findByRole('button', { name: 'Modifica ODL' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.clear(within(dialog).getByLabelText('Nome *'))
    await userEvent.type(within(dialog).getByLabelText('Nome *'), 'Maria')
    expect(within(dialog).queryByLabelText('Stato')).toBeNull()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salva modifiche' }))
    expect(await screen.findByText('Maria Rossi')).toBeTruthy()
    expect(api.update).toHaveBeenCalledWith(order.id, expect.objectContaining({ user_first_name: 'Maria' }))
    await userEvent.click(screen.getByRole('button', { name: 'Elimina' }))
    expect(remove).not.toHaveBeenCalled()
    expect(within(screen.getByRole('dialog')).getByText(`Eliminare ${order.code}?`)).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Annulla' }))
    expect(remove).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Elimina' }))
    await userEvent.click(screen.getByRole('button', { name: 'Conferma eliminazione' }))
    expect(await screen.findByText('Nessun ODL da mostrare')).toBeTruthy()
  })
  it(`${Page.name}: quick reminder updates count with demo attribution`, async () => {
    vi.spyOn(api, 'addReminder').mockImplementation(async () => {
      vi.mocked(api.list).mockResolvedValue([{ ...order, reminders_count: 2 }])
      return { id: 2, work_order_id: order.id, created_by: 4, text: 'Richiesta aggiornamenti', created_at: order.created_at }
    })
    render(<Page />)
    await userEvent.click(await screen.findByRole('button', { name: 'Sollecito' }))
    expect(api.addReminder).not.toHaveBeenCalled()
    const dialog = screen.getByRole('dialog', { name: 'Aggiungi sollecito' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Annulla' }))
    expect(api.addReminder).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Sollecito' }))
    const reopened = screen.getByRole('dialog')
    await userEvent.type(within(reopened).getByLabelText('Motivo / informazioni del sollecito'), 'Richiesta aggiornamenti')
    await userEvent.click(within(reopened).getByRole('button', { name: 'Aggiungi sollecito' }))
    expect(await screen.findByText('Sollecito aggiunto.')).toBeTruthy()
    await waitFor(() => expect(screen.getByText(order.code).closest('tr')!.querySelector('[data-label="Solleciti"]')!.textContent).toBe('2'))
    expect(api.addReminder).toHaveBeenCalledWith(order.id, 4, 'Richiesta aggiornamenti')
  })
}
it('disables quick reminders with invalid demo configuration', async () => {
  vi.stubEnv('VITE_DEMO_USER_ID', '0')
  render(<Dashboard />)
  expect((await screen.findByRole('button', { name: 'Sollecito' }) as HTMLButtonElement).disabled).toBe(true)
  expect(screen.getByText('Solleciti non disponibili: utente demo non configurato.')).toBeTruthy()
})
it('preserves edit form after conflict and shows deletion 404 cleanly', async () => {
  vi.spyOn(api, 'update').mockRejectedValue(new ApiError('Conflitto ODL', 409))
  vi.spyOn(api, 'delete').mockRejectedValue(new ApiError('ODL non trovato', 404))
  render(<WorkOrders />)
  await userEvent.click(await screen.findByRole('button', { name: 'Modifica ODL' }))
  await userEvent.click(screen.getByRole('button', { name: 'Salva modifiche' }))
  expect(await screen.findByText('Conflitto ODL')).toBeTruthy()
  expect(screen.getByRole('dialog')).toBeTruthy()
  await userEvent.click(screen.getByRole('button', { name: 'Annulla' }))
  await userEvent.click(screen.getByRole('button', { name: 'Elimina' }))
  await userEvent.click(screen.getByRole('button', { name: 'Conferma eliminazione' }))
  expect(await screen.findByText('ODL non trovato')).toBeTruthy()
})
it('detail adds separate notes, refreshes history, edits and returns to list on delete', async () => {
  vi.spyOn(api, 'addNote').mockImplementation(async (id, text) => {
    const note = { id: 1, work_order_id: id, text, created_at: order.created_at, created_by: null }
    vi.mocked(api.notes).mockResolvedValue([note]); return note
  })
  vi.spyOn(api, 'update').mockImplementation(async (_id, data) => {
    const updated = { ...order, ...data }; vi.mocked(api.get).mockResolvedValue(updated); return updated
  })
  vi.spyOn(api, 'delete').mockResolvedValue(undefined)
  render(<WorkOrderDetail id={order.id} />)
  await userEvent.type(await screen.findByLabelText('Nuova nota'), 'Informazioni aggiuntive')
  await userEvent.click(screen.getByRole('button', { name: 'Aggiungi nota' }))
  expect(await screen.findByText('Informazioni aggiuntive')).toBeTruthy()
  expect(screen.getByText(order.description)).toBeTruthy()
  await waitFor(() => expect(api.history).toHaveBeenCalledTimes(2))
  await userEvent.click(screen.getByRole('button', { name: 'Modifica ODL' }))
  await userEvent.clear(screen.getByLabelText('Telefono *'))
  await userEvent.type(screen.getByLabelText('Telefono *'), '999')
  await userEvent.click(screen.getByRole('button', { name: 'Salva modifiche' }))
  expect(await screen.findByRole('link', { name: '999' })).toBeTruthy()
  await userEvent.click(screen.getByRole('button', { name: 'Elimina' }))
  await userEvent.click(screen.getByRole('button', { name: 'Conferma eliminazione' }))
  await waitFor(() => expect(window.location.hash).toBe('#/odl'))
})
it('technician updates name and contact fields; routing stays read-only', async () => {
  const technician = { id: 1, first_name: 'Mario', last_name: 'Rossi', phone: '123', email: null, category_id: 2, category_name: 'Idraulico', escalation_order: 1, is_team_leader: false }
  vi.spyOn(api, 'technicians').mockResolvedValue([technician])
  vi.spyOn(api, 'updateTechnician').mockImplementation(async (_id, data) => {
    const updated = { ...technician, ...data }; vi.mocked(api.technicians).mockResolvedValue([updated]); return updated
  })
  render(<Technicians />)
  await userEvent.click(await screen.findByRole('button', { name: 'Modifica' }))
  const dialog = screen.getByRole('dialog')
  expect(within(dialog).getByText(/sola lettura/)).toBeTruthy()
  expect(within(dialog).queryByRole('combobox')).toBeNull()
  await userEvent.clear(screen.getByLabelText('Nome *')); await userEvent.type(screen.getByLabelText('Nome *'), 'Marco')
  await userEvent.clear(screen.getByLabelText('Telefono *')); await userEvent.type(screen.getByLabelText('Telefono *'), '456')
  await userEvent.type(screen.getByLabelText('Email'), 'marco@example.com')
  await userEvent.click(screen.getByRole('button', { name: 'Salva modifiche' }))
  expect(await screen.findByText('Marco Rossi')).toBeTruthy()
  expect(screen.getByText('456')).toBeTruthy()
  expect(api.updateTechnician).toHaveBeenCalledWith(1, { first_name: 'Marco', last_name: 'Rossi', phone: '456', email: 'marco@example.com' })
})
it('DELETE client accepts the existing 204 response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
  await expect(api.delete(1)).resolves.toBeUndefined()
  vi.unstubAllGlobals()
})

it('notes appear before the add-note heading and form', async () => {
  vi.mocked(api.notes).mockResolvedValue([{ id: 2, work_order_id: 1, text: 'Nota recente', created_at: order.created_at, created_by: null }, { id: 1, work_order_id: 1, text: 'Nota precedente', created_at: order.created_at, created_by: null }])
  render(<WorkOrderDetail id={1} />)
  const recent = await screen.findByText('Nota recente')
  const older = screen.getByText('Nota precedente')
  const heading = screen.getByRole('heading', { name: 'Aggiungi nota' })
  const form = screen.getByLabelText('Nuova nota')
  expect(recent.compareDocumentPosition(older) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(older.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(heading.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})
it('empty notes state precedes add-note form', async () => {
  render(<WorkOrderDetail id={1} />)
  const empty = await screen.findByText('Nessuna nota presente.')
  expect(empty.compareDocumentPosition(screen.getByLabelText('Nuova nota')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})
it('detail reminder cancellation and whitespace input do not create records', async () => {
  const add = vi.spyOn(api, 'addReminder')
  render(<WorkOrderDetail id={1} />)
  await userEvent.click(await screen.findByRole('button', { name: 'Aggiungi sollecito' }))
  const dialog = screen.getByRole('dialog')
  await userEvent.type(within(dialog).getByLabelText('Motivo / informazioni del sollecito'), '   ')
  expect((within(dialog).getByRole('button', { name: 'Aggiungi sollecito' }) as HTMLButtonElement).disabled).toBe(true)
  await userEvent.click(within(dialog).getByRole('button', { name: 'Annulla' }))
  expect(add).not.toHaveBeenCalled()
})
it('failed reminder keeps text and error in dialog without claiming success', async () => {
  vi.spyOn(api, 'addReminder').mockRejectedValue(new ApiError('Utente del sollecito non trovato', 422))
  render(<Dashboard />)
  await userEvent.click(await screen.findByRole('button', { name: 'Sollecito' }))
  const dialog = screen.getByRole('dialog')
  await userEvent.type(within(dialog).getByLabelText('Motivo / informazioni del sollecito'), 'Richiesta aggiornamenti')
  await userEvent.click(within(dialog).getByRole('button', { name: 'Aggiungi sollecito' }))
  expect(await screen.findByText('Utente del sollecito non trovato')).toBeTruthy()
  expect((screen.getByLabelText('Motivo / informazioni del sollecito') as HTMLTextAreaElement).value).toBe('Richiesta aggiornamenti')
  expect(screen.queryByText('Sollecito aggiunto.')).toBeNull()
})
