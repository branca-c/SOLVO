export function demoReminderUserId() {
  const value = String(import.meta.env.VITE_DEMO_USER_ID ?? '').trim()
  return /^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : undefined
}
