/** Race types — 5-tag system. */

export interface RaceListItem {
  id: number
  name: string
  date: string
  age_range: string
  sex_restriction: string
  race_grade: string
  country: string
  distance: number
  surface: string
  status: RaceStatus
  is_hidden: boolean
  horse_count: number
  vote_count: number
  has_voted: boolean
  created_at: string
  custom_scoring?: CustomScoring | null
}

export interface RaceDetail {
  id: number
  name: string
  date: string
  age_range: string
  sex_restriction: string
  race_grade: string
  country: string
  distance: number
  surface: string
  status: RaceStatus
  is_hidden: boolean
  custom_scoring: CustomScoring | null
  horses: RaceHorseSnapshot[]
  horse_votes?: RaceDetailHorseVotes | null  // only for settled races
  vote_count: number
  created_at: string
}

export interface RaceHorseSnapshot {
  horse_id: number
  race_horse_id: number
  snapshot_data: HorseSnapshotData
  position: number | null
  gate: number | null
  jockey: string | null
}

export interface PublicResultVote {
  username: string
  points: number | null
}

export interface RaceHorseResult {
  race_horse_id: number
  horse_id: number
  snapshot_data: Record<string, any>
  position: number | null
  jockey: string | null
  votes: PublicResultVote[]
}

export interface RaceDetailHorseVotes {
  horses: RaceHorseResult[]
}

export interface HorseSnapshotData {
  name: string
  sex: string | null
  birth_year: number | null
  origin: string | null
  hemisphere: string | null
  location: string | null
  sire: string | null
  damsire: string | null
  previous_result: string | null
  previous_result_date: string | null
  previous_result_position: number | null
  best_win: string | null
  best_win_date: string | null
}

export interface CustomScoring {
  positive_scores: number[]
  penalty_rules?: PenaltyRule[] | null
}

export interface PenaltyRule {
  position: number
  points: number
}

export type Grade = 'G1' | 'G2_JPN1' | 'YOUNG_G1' | 'CUSTOM'
export type RaceStatus = 'voting' | 'locked' | 'settled'

export interface RaceCreatePayload {
  name: string
  date: string
  age_range: string
  sex_restriction: string
  race_grade: string
  country: string
  distance: number
  surface: string
  horse_ids?: number[] | null
  horse_jockeys?: Record<string, string> | null
  custom_scoring?: CustomScoring | null
  is_hidden?: boolean
}

export interface RaceUpdatePayload {
  name?: string
  date?: string
  age_range?: string
  sex_restriction?: string
  race_grade?: string
  country?: string
  distance?: number
  surface?: string
  horse_ids?: number[] | null
  horse_jockeys?: Record<string, string> | null
  custom_scoring?: CustomScoring | null
}

export interface RaceHorseUpdatePayload {
  jockey?: string | null
}

export interface AddRaceHorsePayload {
  horse_id: number
  jockey?: string | null
}

export interface GateOrderPayload {
  order: number[]
}

/** Result entry types */
export interface ResultPosition {
  race_horse_id: number
  position: number  // 0 = DNF, 1+ = finishing order
}

export interface UserScore {
  user_id: number
  username: string
  points: number
}

export interface ResultEntryResponse {
  race_id: number
  status: string
  scores: UserScore[]
}
