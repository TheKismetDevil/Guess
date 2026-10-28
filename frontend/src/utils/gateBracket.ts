/**
 * JRA bracket (枠番) for a horse number, plus the bracket's saddle-cloth colour.
 *
 * Up to 8 runners each horse has its own bracket. With 9–18 runners the
 * remainder is spread over the outside brackets, so e.g. 12 runners put
 * horses 1–4 alone in brackets 1–4 and pair the rest in brackets 5–8.
 */

const BRACKET_COLORS: Record<number, { bg: string; fg: string }> = {
  1: { bg: '#FFFFFF', fg: '#1A2E1A' },
  2: { bg: '#222222', fg: '#FFFFFF' },
  3: { bg: '#E0382F', fg: '#FFFFFF' },
  4: { bg: '#1E66C1', fg: '#FFFFFF' },
  5: { bg: '#F5CF2C', fg: '#1A2E1A' },
  6: { bg: '#2E9A4E', fg: '#FFFFFF' },
  7: { bg: '#EF7D22', fg: '#FFFFFF' },
  8: { bg: '#EE86B0', fg: '#FFFFFF' },
}

export function gateBracket(gate: number, fieldSize: number): number | null {
  if (gate < 1 || gate > fieldSize || fieldSize < 1 || fieldSize > 18) return null
  if (fieldSize <= 8) return gate

  const base = Math.floor(fieldSize / 8)
  const extra = fieldSize % 8
  let last = 0
  for (let bracket = 1; bracket <= 8; bracket++) {
    last += base + (bracket > 8 - extra ? 1 : 0)
    if (gate <= last) return bracket
  }
  return null
}

export function gateBracketColor(gate: number, fieldSize: number): { bg: string; fg: string } | null {
  const bracket = gateBracket(gate, fieldSize)
  return bracket === null ? null : BRACKET_COLORS[bracket]
}
