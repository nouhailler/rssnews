import { useState, useRef, useEffect } from 'react'

export default function TTSBar({ text }) {
  const [state, setState]   = useState('idle')  // idle | playing | paused
  const [speed, setSpeed]   = useState(1.0)
  const [supported, setSupported] = useState(true)
  const uttRef = useRef(null)

  useEffect(() => {
    if (!('speechSynthesis' in window)) setSupported(false)
    return () => { window.speechSynthesis?.cancel() }
  }, [])

  useEffect(() => {
    // Stop playback when article changes
    stop()
  }, [text])

  const play = () => {
    if (!text || !supported) return
    window.speechSynthesis.cancel()

    const utt = new SpeechSynthesisUtterance(stripHtml(text))
    utt.lang  = 'fr-FR'
    utt.rate  = speed
    utt.onend = () => setState('idle')
    utt.onerror = () => setState('idle')

    uttRef.current = utt
    window.speechSynthesis.speak(utt)
    setState('playing')
  }

  const pause = () => {
    window.speechSynthesis.pause()
    setState('paused')
  }

  const resume = () => {
    window.speechSynthesis.resume()
    setState('playing')
  }

  const stop = () => {
    window.speechSynthesis.cancel()
    setState('idle')
  }

  const handleSpeed = (e) => {
    const v = parseFloat(e.target.value)
    setSpeed(v)
    if (state === 'playing') {
      stop()
      setTimeout(() => {
        const utt = new SpeechSynthesisUtterance(stripHtml(text))
        utt.lang  = 'fr-FR'
        utt.rate  = v
        utt.onend = () => setState('idle')
        uttRef.current = utt
        window.speechSynthesis.speak(utt)
        setState('playing')
      }, 100)
    }
  }

  if (!supported) return (
    <div className="tts-bar">
      <span className="tts-bar-label">🔇 Synthèse vocale non supportée par ce navigateur</span>
    </div>
  )

  return (
    <div className="tts-bar">
      <span className="tts-bar-label">🔊 TTS</span>
      {state === 'idle' && (
        <button className="btn" onClick={play} disabled={!text}>▶ Lire</button>
      )}
      {state === 'playing' && (
        <button className="btn" onClick={pause}>⏸ Pause</button>
      )}
      {state === 'paused' && (
        <button className="btn" onClick={resume}>▶ Reprendre</button>
      )}
      {state !== 'idle' && (
        <button className="btn" onClick={stop}>⏹ Stop</button>
      )}
      <span className="tts-bar-label">Vitesse :</span>
      <select className="tts-speed" value={speed} onChange={handleSpeed}>
        {[0.75, 1.0, 1.25, 1.5, 1.75, 2.0].map(v => (
          <option key={v} value={v}>{v}×</option>
        ))}
      </select>
      {state === 'playing' && <span className="tts-bar-label spin">🎙</span>}
      {state === 'paused'  && <span className="tts-bar-label">⏸</span>}
    </div>
  )
}

function stripHtml(html) {
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}
