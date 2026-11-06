/** Leaderboard API calls. */

import apiClient from './client'
import type { LeaderboardEntry, LeaderboardFilters, LeaderboardRace, LeaderboardSort, ComparisonParticipant, HeadToHeadResult } from '@/types/leaderboard'

function filterParams(filters?: LeaderboardFilters): Record<string, string | number | string[]> {
  const params: Record<string, string | number | string[]> = {}
  if (filters) {
    if (filters.age_range?.length) params.age_range = filters.age_range
    if (filters.sex_restriction?.length) params.sex_restriction = filters.sex_restriction
    if (filters.race_grade?.length) params.race_grade = filters.race_grade
    if (filters.country?.length) params.country = filters.country
    if (filters.surface?.length) params.surface = filters.surface
    if (filters.distance_min !== undefined) params.distance_min = filters.distance_min
    if (filters.distance_max !== undefined) params.distance_max = filters.distance_max
    if (filters.horse_count_min !== undefined) params.horse_count_min = filters.horse_count_min
    if (filters.horse_count_max !== undefined) params.horse_count_max = filters.horse_count_max
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to
  }
  return params
}

export async function getLeaderboard(filters?: LeaderboardFilters, sortBy: LeaderboardSort = 'total_points'): Promise<LeaderboardEntry[]> {
  const response = await apiClient.get('/leaderboard', { params: { ...filterParams(filters), sort_by: sortBy } })
  return response.data.data as LeaderboardEntry[]
}

export async function getLeaderboardRaces(filters?: LeaderboardFilters): Promise<LeaderboardRace[]> {
  const response = await apiClient.get('/leaderboard/races', { params: filterParams(filters) })
  return response.data.data as LeaderboardRace[]
}

export async function getComparisonParticipants(): Promise<ComparisonParticipant[]> {
  return (await apiClient.get<{ data: ComparisonParticipant[] }>('/leaderboard/participants')).data.data
}

export async function getHeadToHead(participantIds: string[], filters?: LeaderboardFilters): Promise<HeadToHeadResult> {
  return (await apiClient.get<{ data: HeadToHeadResult }>('/leaderboard/head-to-head', {
    params: { ...filterParams(filters), participant_id: participantIds },
  })).data.data
}
