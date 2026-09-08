// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CreateWorkOrder } from '../pages/CreateWorkOrder'
import { api } from '../services/api'
import { order } from './fixtures'
import type { WorkOrderDraft } from '../types/workOrder'

const draft: WorkOrderDraft = {
  user_first_name: 'Ada', user_last_name: 'Rossi', user_phone: '3331234567', user_email: null,
  fault_address: 'Via Roma 12', category_id: 2, category_name: 'Idraulico', priority: 'MEDIA',
  description: 'Perdita dal tubo del bagno.', warnings: ['Verifica i dati prima di confermare.'],
}
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('analyzes into the editable form and creates only on explicit confirmation', async () => {
  const analyze = vi.spyOn(api, 'draft').mockResolvedValue(draft)
  const create = vi.spyOn(api, 'create').mockResolvedValue(order)
  const onCreated = vi.fn()
  render(<CreateWorkOrder onCreated={onCreated} />)
  await userEvent.click(screen.getByRole('button', { name: 'Assistito da AI' }))
  expect(screen.queryByRole('button', { name: 'Conferma e crea ODL' })).toBeNull()
  const text = 'Mi chiamo Ada Rossi, telefono 3331234567. Perdita dal tubo in Via Roma 12.'
  await userEvent.type(screen.getByLabelText('Descrizione libera del guasto'), text)
  await userEvent.click(screen.getByRole('button', { name: 'Analizza con AI' }))
  await screen.findByText('Bozza pronta: rivedi e conferma i dati.')
  expect(analyze).toHaveBeenCalledWith(text, expect.any(AbortSignal))
  expect(create).not.toHaveBeenCalled()
  expect(onCreated).not.toHaveBeenCalled()
  expect((screen.getByLabelText('Nome *') as HTMLInputElement).value).toBe('Ada')
  expect((screen.getByLabelText('ID categoria *') as HTMLInputElement).value).toBe('2')
  expect(screen.getByText('Verifica i dati prima di confermare.')).toBeTruthy()
  await userEvent.clear(screen.getByLabelText('Cognome *'))
  await userEvent.type(screen.getByLabelText('Cognome *'), 'Bianchi')
  await userEvent.selectOptions(screen.getByLabelText('Priorità *'), 'ALTA')
  await userEvent.click(screen.getByRole('button', { name: 'Conferma e crea ODL' }))
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(order.id))
  expect(create).toHaveBeenCalledTimes(1)
  expect(create).toHaveBeenCalledWith({
    user_first_name: 'Ada', user_last_name: 'Bianchi', user_phone: '3331234567', user_email: null,
    fault_address: 'Via Roma 12', category_id: 2, priority: 'ALTA', description: draft.description,
  })
})

it('leaves missing fields and priority empty and requires completion', async () => {
  vi.spyOn(api, 'draft').mockResolvedValue({ ...draft, user_phone: null, category_id: null, category_name: null, priority: null })
  const create = vi.spyOn(api, 'create')
  render(<CreateWorkOrder onCreated={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Assistito da AI' }))
  await userEvent.type(screen.getByLabelText('Descrizione libera del guasto'), 'Guasto')
  await userEvent.click(screen.getByRole('button', { name: 'Analizza con AI' }))
  await screen.findByText('Bozza pronta: rivedi e conferma i dati.')
  expect((screen.getByLabelText('Telefono *') as HTMLInputElement).value).toBe('')
  expect((screen.getByLabelText('Priorità *') as HTMLSelectElement).value).toBe('')
  await userEvent.click(screen.getByRole('button', { name: 'Conferma e crea ODL' }))
  expect(create).not.toHaveBeenCalled()
})

it('shows loading and an error, preserves source text and allows retry', async () => {
  let reject: (reason: Error) => void = () => {}
  vi.spyOn(api, 'draft').mockImplementationOnce(() => new Promise((_, fail) => { reject = fail }))
    .mockResolvedValueOnce(draft)
  render(<CreateWorkOrder onCreated={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Assistito da AI' }))
  await userEvent.type(screen.getByLabelText('Descrizione libera del guasto'), 'Testo originale del guasto')
  await userEvent.click(screen.getByRole('button', { name: 'Analizza con AI' }))
  expect(screen.getByText('Analisi del testo in corso…')).toBeTruthy()
  expect((screen.getByRole('button', { name: 'Analisi in corso…' }) as HTMLButtonElement).disabled).toBe(true)
  reject(new Error('Analisi non disponibile'))
  await screen.findByText('Analisi non disponibile')
  expect((screen.getByLabelText('Descrizione libera del guasto') as HTMLTextAreaElement).value).toBe('Testo originale del guasto')
  await userEvent.click(screen.getByRole('button', { name: 'Analizza con AI' }))
  await screen.findByText('Bozza pronta: rivedi e conferma i dati.')
})

it('preserves manual edits when changing modes without analyzing', async () => {
  const analyze = vi.spyOn(api, 'draft')
  render(<CreateWorkOrder onCreated={vi.fn()} />)
  await userEvent.type(screen.getByLabelText('Nome *'), 'Giulia')
  await userEvent.click(screen.getByRole('button', { name: 'Assistito da AI' }))
  await userEvent.click(screen.getByRole('button', { name: 'Inserimento manuale' }))
  expect((screen.getByLabelText('Nome *') as HTMLInputElement).value).toBe('Giulia')
  expect(analyze).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Crea ODL' })).toBeTruthy()
})

it('aborts analysis when leaving the creation page', async () => {
  let signal: AbortSignal | undefined
  vi.spyOn(api, 'draft').mockImplementation((_text, requestSignal) => {
    signal = requestSignal
    return new Promise(() => {})
  })
  const { unmount } = render(<CreateWorkOrder onCreated={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Assistito da AI' }))
  await userEvent.type(screen.getByLabelText('Descrizione libera del guasto'), 'Guasto')
  await userEvent.click(screen.getByRole('button', { name: 'Analizza con AI' }))
  unmount()
  expect(signal?.aborted).toBe(true)
})

it('uploads audio, shows transcript and requires editable confirmation', async () => {
  const audio = vi.spyOn(api, 'audioDraft').mockResolvedValue({ transcript: 'Perdita dal tubo.', draft })
  const create = vi.spyOn(api, 'create').mockResolvedValue(order)
  render(<CreateWorkOrder onCreated={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Assistito da AI' }))
  const file = new File(['audio'], 'guasto.webm', { type: 'audio/webm' })
  await userEvent.upload(screen.getByLabelText('File audio'), file)
  await userEvent.click(screen.getByRole('button', { name: 'Trascrivi e analizza' }))
  await screen.findByText('Perdita dal tubo.')
  expect(audio).toHaveBeenCalledWith(file, expect.any(AbortSignal))
  expect(create).not.toHaveBeenCalled()
  expect((screen.getByLabelText('Nome *') as HTMLInputElement).value).toBe('Ada')
  await userEvent.clear(screen.getByLabelText('Nome *'))
  await userEvent.type(screen.getByLabelText('Nome *'), 'Maria')
  await userEvent.click(screen.getByRole('button', { name: 'Conferma e crea ODL' }))
  expect(create).toHaveBeenCalledWith(expect.objectContaining({ user_first_name: 'Maria' }))
})

it('keeps file upload usable when microphone permission is denied', async () => {
  vi.stubGlobal('MediaRecorder', class { static isTypeSupported() { return true } })
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockRejectedValue(new Error('denied')) } })
  render(<CreateWorkOrder onCreated={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Assistito da AI' }))
  await userEvent.click(screen.getByRole('button', { name: 'Registra audio' }))
  await screen.findByText('Microfono non disponibile o permesso negato. Puoi caricare un file audio.')
  expect((screen.getByLabelText('File audio') as HTMLInputElement).disabled).toBe(false)
  vi.unstubAllGlobals()
})

it('records, stops microphone tracks and uploads the resulting file', async () => {
  const stop = vi.fn()
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }) } })
  class Recorder {
    static isTypeSupported() { return true }
    state = 'inactive'
    ondataavailable?: (event: { data: Blob }) => void
    onstop?: () => void
    start() { this.state = 'recording' }
    stop() { this.state = 'inactive'; this.ondataavailable?.({ data: new Blob(['audio']) }); this.onstop?.() }
  }
  vi.stubGlobal('MediaRecorder', Recorder)
  const audio = vi.spyOn(api, 'audioDraft').mockResolvedValue({ transcript: 'Audio registrato', draft })
  render(<CreateWorkOrder onCreated={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: 'Assistito da AI' }))
  await userEvent.click(screen.getByRole('button', { name: 'Registra audio' }))
  await screen.findByText('Registrazione in corso…')
  await userEvent.click(screen.getByRole('button', { name: 'Ferma registrazione' }))
  expect(stop).toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: 'Trascrivi e analizza' }))
  await screen.findByText('Audio registrato')
  expect(audio.mock.calls[0][0].type).toBe('audio/webm')
  vi.unstubAllGlobals()
})
