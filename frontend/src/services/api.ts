import type { HealthResponse } from '../types'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export async function getHealth(signal: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`, { signal })
  if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`)
  const payload: unknown = await response.json()
  if (
    typeof payload !== 'object' || payload === null ||
    !('status' in payload) || payload.status !== 'ok' ||
    !('service' in payload) || payload.service !== 'proofloop'
  ) throw new Error('Backend health response does not match the ProofLoop contract')
  return { status: 'ok', service: 'proofloop' }
}
