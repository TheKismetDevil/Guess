import api from './client'

import type { ImportPreview, ImportBatch, HistoryRace, HistoryScore, ImportDecision, HistoryImportOptions } from '@/types/historical'

const uploadHeaders = { 'Content-Type': 'application/octet-stream' }
export async function previewHistory(content: ArrayBuffer, options: HistoryImportOptions) {
  return (await api.post<{ data: ImportPreview }>('/admin/historical-scores/preview', content, { headers: uploadHeaders, params: options })).data.data
}
export async function importHistory(content: ArrayBuffer, filename: string, preview_token: string, decisions: Record<string, ImportDecision>, options: HistoryImportOptions) {
  return (await api.post<{ data: { imported_races: number; imported_scores: number; updated_races: number; skipped_races: string[] } }>('/admin/historical-scores', content,
    { headers: uploadHeaders, params: { filename, preview_token, decisions: JSON.stringify(decisions), ...options } })).data.data
}
export async function getHistoryBatches() {
  return (await api.get<{ data: ImportBatch[] }>('/admin/historical-batches')).data.data
}
export async function getBatchRaces(id: number) {
  return (await api.get<{ data: HistoryRace[] }>(`/admin/historical-batches/${id}/races`)).data.data
}
export async function getHistoryScores(id: number) {
  return (await api.get<{ data: HistoryScore[] }>(`/admin/historical-races/${id}/scores`)).data.data
}
export async function saveHistoryScore(id: number, points: number, expected_points: number) {
  return (await api.patch<{ data: HistoryScore }>(`/admin/historical-scores/${id}`, { points, expected_points })).data.data
}
export async function undoHistoryBatch(id: number) {
  return (await api.post(`/admin/historical-batches/${id}/undo`)).data.data
}
