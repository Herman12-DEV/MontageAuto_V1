import { useEffect, useState } from 'react'

export function showToast(message: string) {
  window.dispatchEvent(new CustomEvent<string>('autocut:toast', { detail: message }))
}

export function ToastHost() {
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const handler = (event: Event) => setMessage((event as CustomEvent<string>).detail)
    window.addEventListener('autocut:toast', handler)
    return () => window.removeEventListener('autocut:toast', handler)
  }, [])

  useEffect(() => {
    if (!message) return
    const timer = window.setTimeout(() => setMessage(null), 2800)
    return () => window.clearTimeout(timer)
  }, [message])

  if (!message) return null
  return (
    <div className="toast" role="status">
      {message}
    </div>
  )
}
