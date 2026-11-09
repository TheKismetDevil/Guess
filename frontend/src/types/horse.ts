/** Horse types. */

export interface Horse {
  id: number
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

export interface HorseCreatePayload {
  name: string
  sex?: string | null
  birth_year?: number | null
  origin?: string | null
  hemisphere?: string | null
  location?: string | null
  sire?: string | null
  damsire?: string | null
  previous_result?: string | null
  previous_result_date?: string | null
  previous_result_position?: number | null
  best_win?: string | null
  best_win_date?: string | null
}

export interface HorseUpdatePayload {
  name?: string | null
  sex?: string | null
  birth_year?: number | null
  origin?: string | null
  hemisphere?: string | null
  location?: string | null
  sire?: string | null
  damsire?: string | null
  previous_result?: string | null
  previous_result_date?: string | null
  previous_result_position?: number | null
  best_win?: string | null
  best_win_date?: string | null
}

export interface OriginStat {
  origin: string
  count: number
  hemisphere?: string | null
}

export interface LocationStat {
  location: string
  count: number
}
