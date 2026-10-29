/** Leaderboard type definitions. */

export interface LeaderboardEntry {
  username: string
  total_points: number
  races_participated: number
  avg_points: number
}

export interface LeaderboardResponse {
  data: LeaderboardEntry[]
}

export interface LeaderboardFilters {
  date_from?: string
  date_to?: string
  age_range?: string[]
  sex_restriction?: string[]
  race_grade?: string[]
  country?: string[]
  surface?: string[]
  distance_min?: number
  distance_max?: number
  horse_count_min?: number
  horse_count_max?: number
}

export interface LeaderboardRace {
  id: number | null
  name: string
  date: string
  source: 'live' | 'historical'
}
