// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TechnicianAssignment } from '../pages/TechnicianAssignment'
import { NotifyAssignment } from '../components/NotifyAssignment'
import { ActivityPanels } from '../components/ActivityPanels'
import { api, ApiError } from '../services/api'
import type { PublicAssignment } from '../types/workOrder'
import App from '../App'

const assignment: PublicAssignment = {
  id: 1, status: 'PENDING', technician_name: 'Ada Rossi', work_order_code: 'SOLVO-TEST',
  requester_name: 'Luca Bianchi', requester_phone: '+393331234567', fault_address: 'Via Roma 12',
  category: 'Elettrico', priority: 'ALTA', description: 'Guasto elettrico', work_order_status: 'APERTO', rejection_notes: null,
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, '', '/') })

it('renders the direct mobile route without operator layout and accepts', async () => {
  window.history.replaceState({}, '', '/tecnico/assegnazione/signed-token')
  vi.spyOn(api, 'publicAssignment').mockResolvedValue(assignment)
  const accept = vi.spyOn(api, 'publicAccept').mockResolvedValue({ ...assignment, status: 'ACCEPTED', work_order_status: 'IN_CORSO' })
  render(<App />)
  await screen.findByText('SOLVO-TEST')
  expect(screen.queryByText('Dashboard')).toBeNull()
  expect(screen.getByRole('button', { name: 'Rifiuta' })).toBeTruthy()
  await userEvent.click(screen.getByRole('button', { name: 'Accetta intervento' }))
  await screen.findByText('Intervento accettato')
  expect(accept).toHaveBeenCalledWith('signed-token')
  expect(screen.queryByRole('button', { name: 'Accetta intervento' })).toBeNull()
})

it.each(['', 'Non disponibile'])('rejects with optional notes: %s', async notes => {
  vi.spyOn(api, 'publicAssignment').mockResolvedValue(assignment)
  const reject = vi.spyOn(api, 'publicReject').mockResolvedValue({ ...assignment, status: 'REJECTED', rejection_notes: notes || null })
  render(<TechnicianAssignment token="signed" />)
  await screen.findByText('SOLVO-TEST')
  await userEvent.click(screen.getByRole('button', { name: 'Rifiuta' }))
  if (notes) await userEvent.type(screen.getByLabelText('Note del rifiuto (facoltative)'), notes)
  await userEvent.click(screen.getByRole('button', { name: 'Conferma rifiuto' }))
  await screen.findByText('Intervento rifiutato')
  expect(reject).toHaveBeenCalledWith('signed', notes || null)
  expect(screen.getByText(/SOLVO ha inoltrato/)).toBeTruthy()
})

it('shows invalid link feedback', async () => {
  vi.spyOn(api, 'publicAssignment').mockRejectedValue(new ApiError('Link non valido o scaduto.', 404))
  render(<TechnicianAssignment token="bad" />)
  await screen.findByRole('heading', { name: 'Link non valido o scaduto' })
  expect(screen.queryByRole('button', { name: 'Accetta intervento' })).toBeNull()
})

it('does not claim rejection succeeded on routing conflict', async () => {
  vi.spyOn(api, 'publicAssignment').mockResolvedValue(assignment)
  vi.spyOn(api, 'publicReject').mockRejectedValue(new ApiError('Nessun tecnico successivo', 409))
  render(<TechnicianAssignment token="signed" />)
  await screen.findByText('SOLVO-TEST')
  await userEvent.click(screen.getByRole('button', { name: 'Rifiuta' }))
  await userEvent.click(screen.getByRole('button', { name: 'Conferma rifiuto' }))
  await screen.findByText('Nessun tecnico successivo')
  expect(screen.queryByText('Intervento rifiutato')).toBeNull()
})

it('shows terminal assignment states without action buttons', async () => {
  vi.spyOn(api, 'publicAssignment').mockResolvedValue({ ...assignment, work_order_status: 'CHIUSO' })
  render(<TechnicianAssignment token="signed" />)
  await screen.findByText('SOLVO-TEST')
  expect(screen.queryByRole('button', { name: 'Accetta intervento' })).toBeNull()
})

it('operator notifies the pending technician and refreshes history', async () => {
  vi.spyOn(api, 'reminders').mockResolvedValue([])
  const history = vi.spyOn(api, 'history').mockResolvedValue([])
  vi.spyOn(api, 'assignments').mockResolvedValue([{
    id: 1, status: 'PENDING', work_order_id: 1, technician_id: 1, sent_at: '2026-09-01T12:00:00Z', responded_at: null, rejection_notes: null, attempt_number: 1,
    technician: { id: 1, first_name: 'Ada', last_name: 'Rossi', phone: '+393331234567', email: null, category_id: 1, escalation_order: 1, is_team_leader: false },
  }])
  const notify = vi.spyOn(api, 'notifyAssignment').mockResolvedValue({ provider: 'mock', message_id: 'mock-1', status: 'simulated', action_url: 'http://localhost:5173/tecnico/assegnazione/token' })
  render(<ActivityPanels id={1} status="APERTO" onChanged={vi.fn()} />)
  await screen.findByRole('button', { name: 'Invia Telegram' })
  await userEvent.click(screen.getByRole('button', { name: 'Invia Telegram' }))
  await screen.findByText('Invio simulato: nessun messaggio Telegram inviato.')
  expect(notify).toHaveBeenCalledWith(1)
  expect(screen.getByRole('link', { name: 'Apri link tecnico' }).getAttribute('href')).toContain('/tecnico/assegnazione/token')
  await waitFor(() => expect(history).toHaveBeenCalledTimes(2))
})

it('operator sees notification failure without false success', async () => {
  vi.spyOn(api, 'notifyAssignment').mockRejectedValue(new ApiError('Invio Telegram non confermato.', 503))
  const onSent = vi.fn()
  render(<NotifyAssignment id={1} onSent={onSent} />)
  await userEvent.click(screen.getByRole('button', { name: 'Invia Telegram' }))
  await screen.findByText('Invio Telegram non confermato.')
  expect(onSent).not.toHaveBeenCalled()
  expect(screen.queryByRole('link', { name: 'Apri link tecnico' })).toBeNull()
})


it('operator sees Telegram submission success and the secure link', async () => {
  vi.spyOn(api, 'notifyAssignment').mockResolvedValue({ provider: 'telegram', message_id: '42', status: 'submitted', action_url: 'https://demo.example/tecnico/assegnazione/signed' })
  const onSent = vi.fn()
  render(<NotifyAssignment id={1} onSent={onSent} />)
  await userEvent.click(screen.getByRole('button', { name: 'Invia Telegram' }))
  await screen.findByText('Notifica inviata a Telegram. Lettura non verificata.')
  expect(onSent).toHaveBeenCalledOnce()
  expect(screen.getByRole('link', { name: 'Apri link tecnico' }).getAttribute('href')).toBe('https://demo.example/tecnico/assegnazione/signed')
})
