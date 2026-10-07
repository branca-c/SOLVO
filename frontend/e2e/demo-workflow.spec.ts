import { expect, test } from '@playwright/test'

test('covers the deterministic demo workflow from gated ODL creation to technician acceptance', async ({ page, context }) => {
  const demoKey = process.env.SOLVO_DEMO_ACCESS_KEY
  if (!demoKey) throw new Error('SOLVO_DEMO_ACCESS_KEY is required by the E2E configuration.')

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Accedi alla demo' })).toBeVisible()
  await page.getByLabel('Chiave di accesso').fill(demoKey)
  await page.getByRole('button', { name: 'Entra nella demo' }).click()
  await expect(page.getByRole('link', { name: 'SOLVO — Dashboard' })).toBeVisible()

  await page.goto('/#/odl/nuovo')
  await page.getByLabel(/^Nome/).fill('E2E')
  await page.getByLabel(/^Cognome/).fill('Workflow')
  await page.getByLabel(/^Telefono/).fill('+39000000001')
  await page.getByLabel(/^Indirizzo del guasto/).fill('Via Test 1')
  await page.getByLabel('Categoria *').selectOption({ label: 'Elettrico' })
  await page.getByLabel('Priorità *').selectOption('MEDIA')
  await page.getByLabel(/^Descrizione del guasto/).fill('Verifica E2E della presa elettrica.')
  await page.getByRole('button', { name: 'Crea ODL' }).click()
  await expect(page).toHaveURL(/#\/odl\/\d+$/)

  const workOrderCode = await page.locator('.detail-code').textContent()
  await expect(page.locator('.order-details .badges')).toContainText('APERTO')
  await page.getByRole('button', { name: 'Assegna tecnico' }).click()
  await expect(page.getByText('Tentativo 1')).toBeVisible()

  await page.getByRole('button', { name: 'Nessuna risposta' }).click()
  await expect(page.getByText('Nessuna risposta registrata. Assegnazione avanzata.')).toBeVisible()
  await expect(page.getByText('Tentativo 2')).toBeVisible()

  await page.getByRole('button', { name: 'Invia Telegram' }).click()
  await expect(page.getByText('Invio simulato: nessun messaggio Telegram inviato.')).toBeVisible()
  const actionUrl = await page.getByRole('link', { name: 'Apri link tecnico' }).getAttribute('href')
  expect(actionUrl).toMatch(/^http:\/\/127\.0\.0\.1:5173\/tecnico\/assegnazione\/v1\./)

  const technicianPage = await context.newPage()
  await technicianPage.goto(actionUrl!)
  await expect(technicianPage.getByRole('heading', { name: workOrderCode! })).toBeVisible()
  await technicianPage.getByRole('button', { name: 'Accetta intervento' }).click()
  await expect(technicianPage.getByText('Intervento accettato')).toBeVisible()
  await expect(technicianPage.locator('.badges')).toContainText('IN CORSO')

  await page.reload()
  await expect(page.locator('.order-details .badges')).toContainText('IN CORSO')
})
