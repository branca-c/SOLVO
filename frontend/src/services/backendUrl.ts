function normalizeBackendOrigin(value: string | undefined): string | undefined {
  const origin = value?.trim().replace(/\/+$/, '')
  if (!origin) return undefined
  return origin.endsWith('/api') ? origin.slice(0, -4) : origin
}

export function configuredBackendOrigin(value = import.meta.env.VITE_API_BASE_URL): string | undefined {
  return normalizeBackendOrigin(value)
}

export function apiUrl(path: string, backendOrigin = configuredBackendOrigin()): string {
  const apiPath = path.startsWith('/api/') ? path : `/api${path.startsWith('/') ? path : `/${path}`}`
  const origin = normalizeBackendOrigin(backendOrigin)
  return origin ? `${origin}${apiPath}` : apiPath
}

export function realtimeUrl(backendOrigin = configuredBackendOrigin() ?? window.location.origin): string {
  const url = new URL('/ws/work-orders', normalizeBackendOrigin(backendOrigin) ?? window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}
