// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'
import { api, ApiError } from '../services/api'
import { clearDemoAccessKey, getDemoAccessKey, setDemoAccessKey } from '../services/demoAccess'
import { clearDemoSessionToken, getDemoSessionToken } from '../services/demoSession'

afterEach(() => {
  cleanup()
  clearDemoAccessKey()
  clearDemoSessionToken()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  window.history.replaceState({}, '', '/')
})

it('shows the access screen when the browser session has no demo key', () => {
  render(<App />)
  expect(screen.getByRole('heading', { name: 'Accedi alla demo' })).toBeTruthy()
})

it('stores an entered key for the session and opens the normal application', async () => {
  vi.spyOn(api, 'acquireDemoSession').mockResolvedValue({
    enabled: false, session_token: null, expires_at: null, telegram_linked: false,
  })
  vi.spyOn(api, 'list').mockResolvedValue([])
  render(<App />)
  await userEvent.type(screen.getByLabelText('Chiave di accesso'), 'correct-demo-key')
  await userEvent.click(screen.getByRole('button', { name: 'Entra nella demo' }))
  await screen.findByText('La tua operatività, a colpo d’occhio.')
  expect(getDemoAccessKey()).toBe('correct-demo-key')
})

it('shows the exclusive-session busy screen without exposing visitor data', async () => {
  vi.spyOn(api, 'acquireDemoSession').mockRejectedValue(new ApiError(
    'Demo temporaneamente in uso.', 409,
    { detail: { code: 'DEMO_IN_USE', retry_after_seconds: 125 } },
  ))
  render(<App />)
  await userEvent.type(screen.getByLabelText('Chiave di accesso'), 'correct-demo-key')
  await userEvent.click(screen.getByRole('button', { name: 'Entra nella demo' }))
  expect(await screen.findByRole('heading', { name: 'Demo temporaneamente in uso' })).toBeTruthy()
  expect(screen.getByText('Disponibile tra circa 3 min.')).toBeTruthy()
  expect(getDemoSessionToken()).toBeUndefined()
})

it('sends the session key in normal API requests and clears it after a 401', async () => {
  setDemoAccessKey('correct-demo-key')
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Accesso demo non autorizzato.' }), {
    status: 401, headers: { 'Content-Type': 'application/json' },
  }))
  vi.stubGlobal('fetch', fetch)
  render(<App />)
  await screen.findByRole('heading', { name: 'Accedi alla demo' })
  expect(fetch).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
    headers: expect.objectContaining({ 'X-SOLVO-DEMO-KEY': 'correct-demo-key' }),
  }))
  await waitFor(() => expect(getDemoAccessKey()).toBeUndefined())
})

it('does not show the access screen for a signed technician route', async () => {
  window.history.replaceState({}, '', '/tecnico/assegnazione/signed-token')
  vi.spyOn(api, 'publicAssignment').mockResolvedValue({
    id: 1, status: 'PENDING', technician_name: 'Ada Rossi', work_order_code: 'SOLVO-TEST',
    requester_name: 'Luca Bianchi', requester_phone: '+390000000', fault_address: 'Via Roma 1',
    category: 'Elettrico', priority: 'MEDIA', description: 'Guasto', work_order_status: 'APERTO', rejection_notes: null,
  })
  render(<App />)
  await screen.findByText('SOLVO-TEST')
  expect(screen.queryByText('Accedi alla demo')).toBeNull()
})
