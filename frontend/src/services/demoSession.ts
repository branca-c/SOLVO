const storageKey = 'solvo-demo-session-token'
export const demoSessionRejectedEvent = 'solvo-demo-session-rejected'

function storage(): Storage | undefined {
  try { return window.sessionStorage } catch { return undefined }
}

export function getDemoSessionToken(): string | undefined {
  return storage()?.getItem(storageKey) || undefined
}

export function setDemoSessionToken(token: string): void {
  storage()?.setItem(storageKey, token)
}

export function clearDemoSessionToken(): void {
  storage()?.removeItem(storageKey)
}

export function rejectDemoSession(): void {
  clearDemoSessionToken()
  window.dispatchEvent(new Event(demoSessionRejectedEvent))
}
