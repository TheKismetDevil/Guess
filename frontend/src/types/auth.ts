/** Auth-related TypeScript type definitions. */

export interface UserInfo {
  id: number
  username: string
  qq: string
  is_admin: boolean
  /** Opaque QQ avatar key; missing in sessions stored before avatars existed. */
  avatar_key?: string | null
}

export interface RegisterRequest {
  username: string
  password: string
  qq: string
  invite_code: string
}

export interface RegisterResponse {
  access_token: string
  refresh_token: string
  user: UserInfo
}

export interface LoginRequest {
  username?: string
  password?: string
  qq?: string
  invite_code?: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  user: UserInfo
}

export interface TokenRefreshResponse {
  access_token: string
}

export interface ResetPasswordRequest {
  invite_code: string
  new_password: string
}

export interface ResetPasswordResponse {
  user: UserInfo
}
