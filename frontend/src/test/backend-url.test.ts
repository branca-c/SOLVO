// @vitest-environment jsdom
import { expect, it } from 'vitest'
import { apiUrl, realtimeUrl } from '../services/backendUrl'

it('uses a relative API path when no backend origin is configured', () => {
  expect(apiUrl('/categories', '')).toBe('/api/categories')
})

it('builds HTTPS API URLs and normalizes trailing slashes without duplicating /api', () => {
  expect(apiUrl('/categories', 'https://example.com')).toBe('https://example.com/api/categories')
  expect(apiUrl('/categories', 'https://example.com/')).toBe('https://example.com/api/categories')
  expect(apiUrl('/api/categories', 'https://example.com/api/')).toBe('https://example.com/api/categories')
})

it('uses secure WebSockets for an HTTPS backend and plain WebSockets for HTTP', () => {
  expect(realtimeUrl('https://example.com')).toBe('wss://example.com/ws/work-orders')
  expect(realtimeUrl('http://example.com')).toBe('ws://example.com/ws/work-orders')
})

it('uses the current origin for WebSockets when no backend is configured', () => {
  expect(realtimeUrl(window.location.origin)).toBe(
    `${window.location.origin.replace('http:', 'ws:')}/ws/work-orders`,
  )
})
