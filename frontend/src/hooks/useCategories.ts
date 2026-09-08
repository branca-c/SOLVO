import { api } from '../services/api'
import { useResource } from './useResource'
import type { Category } from '../types/referenceData'

// Read-only reference data is shared for this browser session. Failed loads can retry.
let cached: Promise<Category[]> | undefined
export function clearCategoriesCache() { cached = undefined }
function loadCategories() {
  cached ??= api.categories().catch(error => { cached = undefined; throw error })
  return cached
}
export function useCategories() {
  const resource = useResource(loadCategories)
  return { ...resource, nameFor: (id: number) => resource.data?.find(item => item.id === id)?.name
    ?? (resource.loading ? 'Caricamento categoria…' : 'Categoria non disponibile') }
}
export function resolveCategory(categories: Category[], id: number | null, name: string | null): string {
  const byId = categories.find(item => item.id === id)
  if (byId) return String(byId.id)
  const normalize = (value: string) => value.trim().replace(/\s+/g, ' ').toLocaleLowerCase('it')
  const matches = name ? categories.filter(item => normalize(item.name) === normalize(name)) : []
  return matches.length === 1 ? String(matches[0].id) : ''
}
