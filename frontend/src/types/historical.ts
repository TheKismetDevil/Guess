type ScoreValue = { qq: string; display_name: string; points: number }
export type ImportDifference =
  | { kind: 'metadata'; field: string; before: string | number; after: string | number }
  | { kind: 'score'; qq: string; before: ScoreValue | null; after: ScoreValue | null }
export type ImportDecision = 'keep' | 'replace'
export interface HistoryImportOptions { skip_identical: boolean; skip_empty: boolean }
export interface ImportPreview {
  races: { name: string; date: string; race_id: number | null; action: 'import' | 'skip' | 'conflict' | 'reimport'; reason: string; score_count: number; differences: ImportDifference[] }[]
  participants: number
  imported_races: number
  imported_scores: number
  conflicting_races: number
  reimported_races: number
  options: HistoryImportOptions
  skipped_races: string[]
  preview_token: string
}
export interface ImportBatch {
  id: number; filename: string; created_at: string; undone_at: string | null
  race_count: number; score_count: number
  updated_races: number
}
export interface HistoryRace { id: number; name: string; date: string; score_count: number }
export interface HistoryScore { id: number; qq: string; display_name: string; points: number }
