import { useCategories } from '../hooks/useCategories'
export function CategoryName({ id }: { id: number }) {
  const categories = useCategories()
  return <>{categories.nameFor(id)}{categories.error && <button type="button" className="text-link" onClick={categories.reload}>Riprova categoria</button>}</>
}
