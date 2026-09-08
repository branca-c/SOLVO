import { useEffect, useRef, useState } from 'react'
import { api, messageFor } from '../services/api'
import type { WorkOrderDraft } from '../types/workOrder'

export function AudioIntake({ disabled, onDraft, onBusy }: {
  disabled: boolean; onDraft: (draft: WorkOrderDraft) => void; onBusy: (busy: boolean) => void
}) {
  const [file, setFile] = useState<File>()
  const [state, setState] = useState<'idle' | 'requesting' | 'recording' | 'analyzing'>('idle')
  const [error, setError] = useState('')
  const [transcript, setTranscript] = useState('')
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const alive = useRef(true)
  const request = useRef<AbortController | null>(null)
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      request.current?.abort()
      if (recorder.current?.state === 'recording') recorder.current.stop()
      stream.current?.getTracks().forEach(track => track.stop())
    }
  }, [])
  function finish() { if (alive.current) { setState('idle'); onBusy(false) } }
  async function record() {
    setError(''); setState('requesting'); onBusy(true)
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('Registrazione non disponibile in questo browser. Carica un file audio.')
      const mimeType = ['audio/webm', 'audio/mp4'].find(type => MediaRecorder.isTypeSupported(type))
      if (!mimeType) throw new Error('Formato di registrazione non supportato. Carica un file audio.')
      const media = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!alive.current) { media.getTracks().forEach(track => track.stop()); return }
      stream.current = media
      const instance = new MediaRecorder(media, { mimeType })
      recorder.current = instance
      const chunks: Blob[] = []
      let size = 0
      let failed = false
      instance.ondataavailable = event => {
        size += event.data.size
        if (size > 10 * 1024 * 1024) {
          failed = true
          if (alive.current) setError('Registrazione troppo grande: massimo 10 MiB.')
          if (instance.state === 'recording') instance.stop()
        } else chunks.push(event.data)
      }
      instance.onerror = () => {
        failed = true
        if (alive.current) setError('Registrazione non riuscita. Puoi caricare un file audio.')
        media.getTracks().forEach(track => track.stop()); finish()
      }
      instance.onstop = () => {
        media.getTracks().forEach(track => track.stop())
        if (alive.current && !failed) setFile(new File(chunks, `registrazione.${mimeType === 'audio/mp4' ? 'mp4' : 'webm'}`, { type: mimeType }))
        finish()
      }
      instance.start(1000); setState('recording')
    } catch {
      stream.current?.getTracks().forEach(track => track.stop())
      if (alive.current) setError('Microfono non disponibile o permesso negato. Puoi caricare un file audio.')
      finish()
    }
  }
  async function analyze() {
    if (!file || state !== 'idle' || disabled) return
    if (!file.size || file.size > 10 * 1024 * 1024) { setError('Scegli un audio non vuoto, massimo 10 MiB.'); return }
    const controller = new AbortController(); request.current = controller
    setState('analyzing'); onBusy(true); setError('')
    try {
      const result = await api.audioDraft(file, controller.signal)
      if (!controller.signal.aborted) { setTranscript(result.transcript); onDraft(result.draft) }
    } catch (e) { if (!controller.signal.aborted) setError(messageFor(e)) }
    finally { finish() }
  }
  const locked = disabled || state !== 'idle'
  return <section className="surface ai-intake" aria-label="Intake audio">
    <h2>Descrivi il guasto a voce</h2>
    <p>Carica o registra un audio (WebM, WAV, MP3, MP4; massimo 10 MiB). In modalità mock viene usato un testo dimostrativo, senza riconoscimento vocale.</p>
    <label>File audio<input type="file" accept="audio/webm,audio/wav,audio/x-wav,audio/mpeg,audio/mp4" disabled={locked}
      onChange={event => { setFile(event.target.files?.[0]); setError('') }} /></label>
    <div className="heading-actions">
      <button type="button" className="button button-secondary" disabled={locked} onClick={record}>Registra audio</button>
      {state === 'recording' && <button type="button" className="button button-secondary" onClick={() => recorder.current?.stop()}>Ferma registrazione</button>}
      <button type="button" className="button button-primary" disabled={locked || !file} onClick={analyze}>Trascrivi e analizza</button>
    </div>
    <p role="status">{state === 'recording' ? 'Registrazione in corso…' : state === 'requesting' ? 'Accesso al microfono…' : state === 'analyzing' ? 'Trascrizione e analisi…' : file ? `Audio selezionato: ${file.name}` : 'Nessun audio selezionato.'}</p>
    {error && <p role="alert">{error}</p>}
    {transcript && <div><h3>Trascrizione dell’ultima analisi</h3><p className="audio-transcript">{transcript}</p><p>Rivedi e modifica la bozza prima di confermare la creazione.</p></div>}
  </section>
}
