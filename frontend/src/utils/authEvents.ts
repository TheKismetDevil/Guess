/** Lightweight pub/sub to keep Pinia authStore in sync with apiClient without circular imports. */

export type AuthEvent =
  | { type: 'token-refreshed'; accessToken: string }
  | { type: 'auth-cleared' }

type AuthEventListener = (event: AuthEvent) => void

const listeners = new Set<AuthEventListener>()

export function subscribeAuthEvents(listener: AuthEventListener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function emitAuthEvent(event: AuthEvent): void {
  for (const listener of listeners) {
    listener(event)
  }
}
