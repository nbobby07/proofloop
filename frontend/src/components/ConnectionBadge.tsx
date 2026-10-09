import type { ConnectionStatus } from '../hooks/useBackendHealth'

const labels: Record<ConnectionStatus, string> = {
  checking: 'Checking backend', connected: 'Backend connected', unavailable: 'Backend unavailable',
}

export function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  return <span className={`connection connection-${status}`} role="status">
    <span className="status-dot" aria-hidden="true" />{labels[status]}
  </span>
}
