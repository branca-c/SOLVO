import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
export function OperatorDialog({ label, children, onClose, busy }: { label: string; children: ReactNode; onClose: () => void; busy: boolean }) {
  const ref = useRef<HTMLElement>(null)
  const close = useRef(onClose)
  const working = useRef(busy)
  close.current = onClose; working.current = busy
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const dialog = ref.current!
    const controls = () => Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]'))
    ;(controls()[0] ?? dialog).focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !working.current) { event.preventDefault(); close.current() }
      if (event.key === 'Tab') {
        const items = controls(); const first = items[0]; const last = items.at(-1)
        if (!first) { event.preventDefault(); dialog.focus() }
        else if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) { event.preventDefault(); last?.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    dialog.addEventListener('keydown', keydown)
    return () => { dialog.removeEventListener('keydown', keydown); previous?.focus() }
  }, [])
  return createPortal(<div className="operator-overlay"><section ref={ref} tabIndex={-1} className="surface operator-dialog" role="dialog" aria-modal="true" aria-label={label}>{children}</section></div>, document.body)
}
