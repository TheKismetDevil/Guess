<script setup lang="ts">
import { toRef } from 'vue'
import { useHeadToHead } from '@/composables/useHeadToHead'
import type { ComparisonParticipant, LeaderboardFilters } from '@/types/leaderboard'

const props = defineProps<{ filters: LeaderboardFilters }>()
const { people, peopleState, state, selected, search, result, error, visiblePeople, selectedPeople, totals, removePerson, loadPeople, compare } = useHeadToHead(toRef(props, 'filters'))

function participantLabel(person: ComparisonParticipant) {
  const duplicate = people.value.some(p => p.id !== person.id && p.username === person.username)
  return person.username + (person.kind === 'historical' ? `（历史${duplicate ? ` · ${person.id.slice(-6)}` : ''}）` : '')
}
</script>

<template>
  <section id="head-to-head-panel" class="comparison-panel" aria-labelledby="comparison-title">
    <header class="comparison-heading">
      <div><h2 id="comparison-title">Head to Head</h2><p>选择至少两位用户，逐场对比所有人共同参与的已结算比赛。沿用排行榜已应用的筛选，包含历史成绩、0 分和负分。</p></div>
      <button v-if="selected.length" class="ui-btn ui-btn--ghost ui-btn--sm" @click="selected = []">清空选择</button>
    </header>
    <p v-if="peopleState === 'loading'" role="status">正在加载用户…</p>
    <p v-else-if="peopleState === 'empty'">暂无可对比的用户。</p>
    <div v-else-if="peopleState === 'error'" role="alert">用户列表加载失败。<button class="ui-btn ui-btn--ghost ui-btn--sm" @click="loadPeople">重试</button></div>
    <template v-else>
      <label class="search-label" for="comparison-search">选择对比用户（已选 {{ selected.length }} 位）</label>
      <input id="comparison-search" v-model="search" class="search-input" type="search" placeholder="搜索用户名" />
      <fieldset class="people-list">
        <legend class="sr-only">可多选的对比用户</legend>
        <label v-for="person in visiblePeople" :key="person.id" class="person-option" :class="{ selected: selected.includes(person.id) }">
          <input v-model="selected" type="checkbox" :value="person.id" /><span>{{ participantLabel(person) }}</span>
        </label>
        <p v-if="!visiblePeople.length">没有匹配的用户。</p>
      </fieldset>
      <div v-if="selectedPeople.length" class="selected-people" aria-label="已选用户">
        <button v-for="person in selectedPeople" :key="person.id" class="selected-chip" :aria-label="`移除 ${participantLabel(person)}`" @click="removePerson(person.id)">{{ participantLabel(person) }} <span aria-hidden="true">×</span></button>
      </div>
    </template>
    <p v-if="state === 'idle'" class="comparison-hint" role="status">请选择至少两位用户开始对比。</p>
    <p v-else-if="state === 'loading'" role="status">正在查找共同参与的比赛…</p>
    <p v-else-if="state === 'empty'" class="comparison-hint" role="status">当前筛选下，没有所有所选用户都参与且有得分的比赛。</p>
    <div v-else-if="state === 'error'" role="alert">{{ error }} <button class="ui-btn ui-btn--ghost ui-btn--sm" @click="compare">重试对比</button><button class="ui-btn ui-btn--ghost ui-btn--sm" @click="loadPeople">重新加载用户</button></div>
    <template v-else-if="result">
      <p class="common-count" role="status">共同参与 {{ result.races.length }} 场比赛</p>
      <div class="comparison-table" tabindex="0" role="region" aria-label="共同比赛逐场得分对比，可左右滚动">
        <table>
          <caption class="sr-only">每行一场共同比赛，每列一位用户的得分</caption>
          <thead><tr><th scope="col" class="race-column">比赛</th><th v-for="person in result.participants" :key="person.id" scope="col">{{ participantLabel(person) }}</th></tr></thead>
          <tbody><tr v-for="race in result.races" :key="race.key">
            <th scope="row" class="race-column"><span class="race-date">{{ race.date || '日期未公开' }} <span v-if="race.source === 'historical'" class="history-label">历史</span></span><router-link v-if="race.source === 'live' && race.id !== null" :to="`/races/${race.id}`">{{ race.name }}</router-link><span v-else>{{ race.name }}</span></th>
            <td v-for="(score, index) in race.scores" :key="result.participants[index]!.id" :class="{ negative: score < 0, highest: score === Math.max(...race.scores) }">{{ score }}</td>
          </tr></tbody>
          <tfoot><tr><th scope="row" class="race-column">共同场次合计</th><td v-for="(total, index) in totals" :key="result.participants[index]!.id" :class="{ negative: total < 0 }">{{ total }}</td></tr></tfoot>
        </table>
      </div>
    </template>
  </section>
</template>

<style scoped>
.comparison-panel { margin: 0 0 var(--spacing-5); padding: var(--spacing-4); border: 1px solid var(--color-border-hairline); border-radius: var(--rounded-lg); background: var(--color-surface-raised); }
.comparison-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--spacing-3); }
h2 { margin: 0; font-size: 24px; }
p { margin: var(--spacing-3) 0; line-height: 1.6; font-size: 14px; }
.comparison-heading p, .comparison-hint { color: var(--color-ink-secondary); }
.search-label { display: block; font-size: 14px; font-weight: 600; margin: var(--spacing-3) 0 var(--spacing-2); }
.search-input { width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid var(--color-border-strong); border-radius: var(--rounded-md); background: var(--color-surface-base); color: var(--color-ink-primary); font-size: 16px; }
.people-list { display: flex; flex-wrap: wrap; gap: 8px; border: 0; padding: 12px 0; margin: 0; max-height: 200px; overflow-y: auto; }
.person-option { display: inline-flex; align-items: center; gap: 8px; min-height: 42px; padding: 8px 12px; box-sizing: border-box; border: 1px solid var(--color-border-hairline); border-radius: var(--rounded-md); cursor: pointer; font-size: 14px; }
.person-option.selected { border-color: var(--color-primary); background: var(--color-primary-tint); }
.person-option input { accent-color: var(--color-primary); width: 16px; height: 16px; flex-shrink: 0; }
.selected-people { display: flex; flex-wrap: wrap; gap: 8px; margin: var(--spacing-2) 0; }
.selected-chip { display: inline-flex; gap: 10px; align-items: center; padding: 8px 12px; border-radius: var(--rounded-full); border: 1px solid var(--color-primary); background: var(--color-primary-tint); color: var(--color-primary); font-size: 14px; }
.common-count { font-weight: 600; }
.comparison-table { max-height: 600px; overflow: auto; border: 1px solid var(--color-border-hairline); border-radius: var(--rounded-md); }
table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 14px; }
th, td { border-bottom: 1px solid var(--color-border-hairline); padding: 12px 16px; white-space: nowrap; text-align: right; }
th { font-weight: 600; }
thead th { position: sticky; top: 0; z-index: 2; background: var(--color-surface-base); }
.race-column { position: sticky; left: 0; z-index: 1; min-width: 180px; max-width: 280px; white-space: normal; text-align: left; background: var(--color-surface-raised); }
thead .race-column { z-index: 3; background: var(--color-surface-base); }
.race-date { display: block; color: var(--color-ink-secondary); font-size: 12px; font-weight: 400; margin-bottom: 4px; }
.history-label { margin-left: 6px; }
.race-column a { color: var(--color-primary); }
td.highest { background: var(--color-primary-tint); font-weight: 700; }
td.negative { color: var(--color-destructive); }
tfoot td, tfoot th { background: var(--color-surface-base); font-weight: 700; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; clip: rect(0,0,0,0); overflow: hidden; white-space: nowrap; }
@media (max-width: 767px) { .race-column { min-width: 130px; max-width: 180px; } th, td { padding: 10px; } .comparison-heading { flex-wrap: wrap; } }
</style>
