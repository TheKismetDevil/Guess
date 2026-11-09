/** Invite code types. */

export type InviteCodeStatus = 'unused' | 'used'

export interface InviteCode {
  code: string
  status: InviteCodeStatus
  bound_username: string | null
  bound_qq: string | null
  /** Placeholder user (from historical import) waiting to register with this code; such codes cannot be deleted. */
  placeholder_username?: string | null
  created_at: string | null
}
