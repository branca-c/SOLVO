const storageKey = 'solvo-demo-access-key'
export const demoAccessRejectedEvent = 'solvo-demo-access-rejected'

function storage(): Storage | undefined {
  try { return window.sessionStorage } catch { return undefined }
}

export function getDemoAccessKey(): string | undefined {
  return storage()?.getItem(storageKey) || undefined
}

export function setDemoAccessKey(key: string): void {
  storage()?.setItem(storageKey, key)
}

export function clearDemoAccessKey(): void {
  storage()?.removeItem(storageKey)
}

export function rejectDemoAccess(): void {
  clearDemoAccessKey()
  window.dispatchEvent(new Event(demoAccessRejectedEvent))
}
