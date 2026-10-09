import { useCallback, useEffect, useState } from 'react'
import { getHealth } from '../services/api'

export type ConnectionStatus = 'checking' | 'connected' | 'unavailable'

export function useBackendHealth() {
  const [status, setStatus] = useState<ConnectionStatus>('checking')
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const retry = useCallback(() => {
    setStatus('checking')
    setError(null)
    setAttempt(value => value + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timeout = window.setTimeout(() => controller.abort(), 5000)
    getHealth(controller.signal)
      .then(() => { if (active) setStatus('connected') })
      .catch((reason: unknown) => {
        if (!active) return
        setStatus('unavailable')
        setError(reason instanceof Error ? reason.message : 'Cannot reach backend')
      })
      .finally(() => window.clearTimeout(timeout))
    return () => {
      active = false
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [attempt])

  return { status, error, retry }
}
