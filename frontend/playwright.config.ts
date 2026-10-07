import { randomUUID } from 'node:crypto'
import { defineConfig, devices } from '@playwright/test'

const testEnvironment = {
  APP_ENV: 'test',
  DATABASE_URL: 'sqlite:////tmp/solvo-e2e.sqlite3',
  SOLVO_DEMO_ACCESS_ENABLED: 'true',
  SOLVO_DEMO_ACCESS_KEY: randomUUID(),
  ASSIGNMENT_ACTION_SECRET: randomUUID(),
  TECHNICIAN_ACTION_BASE_URL: 'http://127.0.0.1:5173',
  NOTIFICATION_PROVIDER: 'mock',
  AI_PROVIDER: 'mock',
  TRANSCRIPTION_PROVIDER: 'mock',
}

Object.assign(process.env, testEnvironment)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: './.venv/bin/python -m app.scripts.e2e_server',
      cwd: '../backend',
      url: 'http://127.0.0.1:8001/health',
      reuseExistingServer: false,
      env: { ...process.env, ...testEnvironment },
    },
    {
      command: 'npm run dev',
      cwd: '.',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      env: { ...process.env, ...testEnvironment, VITE_API_BASE_URL: 'http://127.0.0.1:8001' },
    },
  ],
})
