/** Vote types. */

export interface VoteRequest {
  race_horse_id: number
}

export interface VoteResponse {
  id: number
  user_id: number
  race_id: number
  race_horse_id: number
  horse_name: string
  created_at: string
  updated_at: string
}

export interface VoteListEntry {
  user_id: number
  username: string
  avatar_key?: string | null
  race_horse_id: number
  horse_name: string
  points?: number | null
  created_at: string
}
