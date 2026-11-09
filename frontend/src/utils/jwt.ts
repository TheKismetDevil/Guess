/** JWT helpers for client-side token inspection. */

export interface JwtPayload {
  sub?: string
  exp?: number
  iat?: number
  [key: string]: unknown
}

export function parseJwt(token: string): JwtPayload | null {
  try {
    const payloadSegment = token.split('.')[1]
    if (!payloadSegment) return null

    const base64 =
      payloadSegment.replace(/-/g, '+').replace(/_/g, '/') +
      '='.repeat((4 - (payloadSegment.length % 4)) % 4)
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((char) => '%' + ('00' + char.charCodeAt(0).toString(16)).slice(-2))
        .join(''),
    )

    return JSON.parse(jsonPayload) as JwtPayload
  } catch {
    return null
  }
}

export function getTokenExpiry(token: string): number | null {
  const payload = parseJwt(token)
  return typeof payload?.exp === 'number' ? payload.exp : null
}

/**
 * Check whether a JWT token is expired (or within `skewSeconds` of expiring).
 * Non-JWT strings without a numeric `exp` claim return false so opaque test tokens
 * fall through to server-side validation.
 */
export function isTokenExpired(token: string, skewSeconds = 0): boolean {
  const exp = getTokenExpiry(token)
  if (exp === null) return false
  return (exp - skewSeconds) * 1000 <= Date.now()
}
