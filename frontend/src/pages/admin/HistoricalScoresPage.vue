<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue'
import axios from 'axios'
import { previewHistory, importHistory, getHistoryBatches, getBatchRaces, getHistoryScores, saveHistoryScore, undoHistoryBatch } from '@/api/historical'
import type { ImportPreview, ImportBatch, HistoryRace, HistoryScore, ImportDifference, ImportDecision, HistoryImportOptions } from '@/types/historical'

type PageState = 'loading' | 'empty' | 'error' | 'success'
const pageState = ref<PageState>('loading')
const batches = ref<ImportBatch[]>([])
const preview = ref<ImportPreview | null>(null)
const content = shallowRef<ArrayBuffer | null>(null)
const filename = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const decisions = ref<Record<string, ImportDecision>>({})
const importOptions = ref<HistoryImportOptions>({ skip_identical: true, skip_empty: true })
const conflicts = computed(() => preview.value?.races.filter(r => r.action === 'conflict') ?? [])
const unresolved = computed(() => conflicts.value.filter(r => !decisions.value[String(r.race_id)]).length)
const replacementCount = computed(() => Object.values(decisions.value).filter(d => d === 'replace').length + (preview.value?.reimported_races ?? 0))
const fieldLabels: Record<string, string> = { age_range: '年龄范围', sex_restriction: '性别限定', race_grade: '比赛等级', country: '国家或地区', surface: '场地', distance: '距离（米）', horse_count: '参赛马匹数' }
function diffLabel(diff: ImportDifference) {
  return diff.kind === 'metadata' ? fieldLabels[diff.field] ?? diff.field : `QQ ${diff.qq}`
}
function diffValue(diff: ImportDifference, side: 'before' | 'after') {
  if (diff.kind === 'metadata') return String(diff[side])
  const score = diff[side]
  return score ? `${score.points} 分` : '无成绩（未参与）'
}
const busy = ref(false)
const message = ref('')
const error = ref('')
const batch = ref<ImportBatch | null>(null)
const races = ref<HistoryRace[]>([])
const race = ref<HistoryRace | null>(null)
const scores = ref<(HistoryScore & { draft: number | string })[]>([])
const detailLoading = ref(false)
const scoreLoading = ref(false)
const detailError = ref('')
const scoreError = ref('')
const undoTarget = ref<ImportBatch | null>(null)
let detailRequest = 0
let scoreRequest = 0

function errorText(err: unknown) {
  return axios.isAxiosError(err) ? err.response?.data?.detail?.message || '操作失败，请重试' : '操作失败，请重试'
}
async function loadBatches() {
  pageState.value = 'loading'
  try {
    batches.value = await getHistoryBatches()
    pageState.value = batches.value.length ? 'success' : 'empty'
  } catch (err) {
    error.value = errorText(err)
    pageState.value = 'error'
  }
}
async function selectFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  filename.value = file.name.slice(0, 200)
  preview.value = null
  content.value = null
  decisions.value = {}
  error.value = ''
  message.value = ''
  if (file.size > 10 * 1024 * 1024) { error.value = '文件不能超过 10 MB'; return }
  busy.value = true
  try {
    const bytes = await file.arrayBuffer()
    preview.value = await previewHistory(bytes, importOptions.value)
    content.value = bytes
  } catch (err) { error.value = errorText(err) }
  finally { busy.value = false }
}
async function refreshPreview() {
  if (!content.value || busy.value) return
  preview.value = null
  decisions.value = {}
  error.value = ''
  message.value = ''
  busy.value = true
  try { preview.value = await previewHistory(content.value, importOptions.value) }
  catch (err) { error.value = errorText(err) }
  finally { busy.value = false }
}
async function confirmImport() {
  if (!preview.value || !content.value || busy.value) return
  if (unresolved.value) { error.value = '请先为每场有差异的比赛作出选择'; return }
  busy.value = true
  error.value = ''
  try {
    const result = await importHistory(content.value, filename.value, preview.value.preview_token, decisions.value, importOptions.value)
    message.value = `新增 ${result.imported_races} 场比赛、${result.imported_scores} 条成绩；更新 ${result.updated_races} 场；保留或跳过 ${result.skipped_races.length} 场。`
      + (result.placeholder_users ? `已为 ${result.placeholder_users} 个未注册 QQ 创建占位用户和邀请码。` : '')
    preview.value = null
    content.value = null
    await loadBatches()
    if (result.updated_races && batch.value) await openBatch(batch.value)
  } catch (err) {
    error.value = errorText(err)
    if (axios.isAxiosError(err) && err.response?.status === 409) {
      preview.value = null
      content.value = null
    }
  } finally { busy.value = false }
}
async function openBatch(item: ImportBatch) {
  const request = ++detailRequest
  ++scoreRequest
  batch.value = item
  race.value = null
  races.value = []
  scores.value = []
  detailError.value = ''
  detailLoading.value = true
  scoreLoading.value = false
  try {
    const data = await getBatchRaces(item.id)
    if (request === detailRequest) races.value = data
  } catch (err) { if (request === detailRequest) detailError.value = errorText(err) }
  finally { if (request === detailRequest) detailLoading.value = false }
}
async function openRace(item: HistoryRace) {
  const request = ++scoreRequest
  race.value = item
  scores.value = []
  scoreError.value = ''
  scoreLoading.value = true
  try {
    const data = await getHistoryScores(item.id)
    if (request === scoreRequest) scores.value = data.map(s => ({ ...s, draft: s.points }))
  } catch (err) { if (request === scoreRequest) scoreError.value = errorText(err) }
  finally { if (request === scoreRequest) scoreLoading.value = false }
}
async function saveScore(score: HistoryScore & { draft: number | string }) {
  const points = score.draft === '' ? NaN : Number(score.draft)
  if (!Number.isInteger(points) || points < -2147483648 || points > 2147483647) {
    error.value = '得分必须是有效整数，未参与比赛请留在原始工作簿中为空。'; return
  }
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const saved = await saveHistoryScore(score.id, points, score.points)
    Object.assign(score, saved, { draft: saved.points })
    message.value = '成绩已保存，排行榜将按最新成绩计算。'
  } catch (err) { error.value = errorText(err) }
  finally { busy.value = false }
}
async function confirmUndo() {
  if (!undoTarget.value || busy.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const id = undoTarget.value.id
    await undoHistoryBatch(id)
    undoTarget.value = null
    ++detailRequest; ++scoreRequest
    batch.value = null; race.value = null; races.value = []; scores.value = []
    detailLoading.value = false; scoreLoading.value = false
    message.value = '已删除该导入批次并回滚对应历史成绩，排行榜已重新计算。'
    await loadBatches()
  } catch (err) { error.value = errorText(err) }
  finally { busy.value = false }
}
onMounted(loadBatches)
</script>

<template>
  <div class="history-page">
    <header class="ui-page-header">
      <div><h1 class="ui-page-title">历史成绩管理</h1><p class="ui-page-subtitle">预览导入、查看批次与修正成绩</p></div>
      <router-link to="/leaderboard" class="ui-btn ui-btn--ghost ui-btn--sm">查看排行榜</router-link>
    </header>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="message" role="status" class="notice">{{ message }}</p>
    <section class="panel">
      <h2>导入历史成绩</h2>
      <p>选择包含“历史得分”和“赛事资料”的 Excel（最多 10 MB）。QQ 号用于关联用户；0 分计入参与场次，空白表示未参与。</p>
      <fieldset class="import-options" :disabled="busy">
        <legend>导入选项</legend>
        <label><input v-model="importOptions.skip_identical" type="checkbox" @change="refreshPreview" />跳过完全相同的比赛记录</label>
        <label><input v-model="importOptions.skip_empty" type="checkbox" @change="refreshPreview" />不导入无成绩的比赛</label>
        <p>两个选项默认勾选，修改后会重新预览并清除差异选择。0 分仍是一条有效成绩；全部成绩为空才属于无成绩比赛。</p>
      </fieldset>
      <div class="upload-box">
        <input ref="fileInput" class="file-input" type="file" accept=".xlsx" tabindex="-1" aria-label="选择历史成绩 Excel 文件" :disabled="busy" @change="selectFile" />
        <button type="button" class="ui-btn ui-btn--primary file-button" :disabled="busy" @click="fileInput?.click()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 16V4m-4 4 4-4 4 4M4 16v4h16v-4" /></svg>
          {{ busy ? '正在处理…' : filename ? '重新选择 Excel' : '选择 Excel 文件' }}
        </button>
        <div class="file-description"><strong>{{ filename || '上传历史成绩工作簿' }}</strong><span>支持 .xlsx · 最大 10 MB · 选择后先预览差异</span></div>
      </div>
      <p v-if="busy" role="status">正在处理，请稍候…</p>
      <div v-if="preview">
        <h3>{{ filename }}</h3>
        <p>{{ preview.participants }} 位参与者 · 新增 {{ preview.imported_races }} 场 / {{ preview.imported_scores }} 条成绩 · 重新导入 {{ preview.reimported_races }} 场 · 待核对 {{ preview.conflicting_races }} 场 · 跳过 {{ preview.skipped_races.length }} 场</p>
        <div class="table-wrap preview-summary"><table><thead><tr><th>比赛</th><th>日期</th><th>成绩数</th><th>处理方式</th></tr></thead>
          <tbody><tr v-for="item in preview.races" :key="item.name"><td>{{ item.name }}</td><td>{{ item.date }}</td><td>{{ item.score_count }}</td><td>{{ item.action === 'import' ? '新增' : item.action === 'conflict' ? '存在差异，请在下方选择' : item.action === 'reimport' ? '内容相同，重新导入' : `跳过：${item.reason}` }}</td></tr></tbody>
        </table></div>
        <section v-for="item in conflicts" :key="item.race_id!" class="diff-card">
          <h3>{{ item.name }} <span class="diff-date">{{ item.date }}</span></h3>
          <div class="table-wrap"><table><thead><tr><th>差异项</th><th>已有内容</th><th>本次文件</th></tr></thead><tbody>
            <tr v-for="(diff, index) in item.differences" :key="index"><th scope="row">{{ diffLabel(diff) }}</th><td class="diff-old">{{ diffValue(diff, 'before') }}</td><td class="diff-new">{{ diffValue(diff, 'after') }}</td></tr>
          </tbody></table></div>
          <fieldset :disabled="busy" class="diff-choices"><legend>这场比赛如何处理？</legend>
            <label :class="{ chosen: decisions[String(item.race_id)] === 'keep' }"><input v-model="decisions[String(item.race_id)]" type="radio" :name="`decision-${item.race_id}`" value="keep" />保留已有内容</label>
            <label :class="{ chosen: decisions[String(item.race_id)] === 'replace' }"><input v-model="decisions[String(item.race_id)]" type="radio" :name="`decision-${item.race_id}`" value="replace" />使用本次文件</label>
          </fieldset>
          <p class="diff-help">选择“使用本次文件”会替换这场比赛的赛事资料和全部历史成绩。文件中为空或缺少的用户成绩会被移除；选择“保留已有”则维持整场比赛的原数据。</p>
        </section>
        <p v-if="unresolved" role="status" class="pending">还有 {{ unresolved }} 场差异未选择。</p>
        <div class="actions"><button class="ui-btn ui-btn--primary" :disabled="busy || unresolved > 0 || (!preview.imported_races && !conflicts.length && !preview.reimported_races)" @click="confirmImport">确认处理（新增 {{ preview.imported_races }} 场 / 更新 {{ replacementCount }} 场）</button><button class="ui-btn ui-btn--ghost" :disabled="busy" @click="preview = null; content = null; decisions = {}">取消</button></div>
      </div>
    </section>

    <section class="panel">
      <h2>导入批次</h2>
      <p v-if="pageState === 'loading'" role="status">正在加载批次…</p>
      <p v-else-if="pageState === 'empty'">暂无历史成绩，请先选择 Excel 预览。</p>
      <button v-else-if="pageState === 'error'" class="ui-btn ui-btn--ghost" @click="loadBatches">加载失败，点击重试</button>
      <div v-else class="table-wrap"><table><thead><tr><th>文件 / 批次</th><th>导入时间</th><th>比赛 / 成绩</th><th>操作</th></tr></thead>
        <tbody><tr v-for="item in batches" :key="item.id"><td>{{ item.filename }}</td><td>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</td><td>{{ item.race_count }} / {{ item.score_count }}<span v-if="item.updated_races" class="batch-updates">另更新 {{ item.updated_races }} 场</span></td><td>
          <button class="ui-btn ui-btn--ghost ui-btn--sm" :disabled="busy" @click="openBatch(item)">查看成绩</button><button class="ui-btn ui-btn--ghost ui-btn--sm danger" :disabled="busy" @click="undoTarget = item">撤销批次</button>
        </td></tr></tbody>
      </table></div>
      <div v-if="undoTarget" class="undo-confirm" role="alert">
        <p>确认撤销「{{ undoTarget.filename }}」？将删除该导入批次记录，移除新增的 {{ undoTarget.race_count }} 场比赛、{{ undoTarget.score_count }} 条成绩，并恢复 {{ undoTarget.updated_races }} 场更新前的数据。若存在后续导入更新或更新后的人工修分，会提示冲突并停止撤销。请保留原始 Excel。</p>
        <div class="actions"><button class="ui-btn ui-btn--danger-solid" :disabled="busy" @click="confirmUndo">确认撤销</button><button class="ui-btn ui-btn--ghost" :disabled="busy" @click="undoTarget = null">取消</button></div>
      </div>
    </section>

    <section v-if="batch" class="panel">
      <h2>{{ batch.filename }} · 比赛</h2>
      <p v-if="detailLoading" role="status">正在加载比赛…</p>
      <p v-else-if="detailError" role="alert">{{ detailError }} <button class="ui-btn ui-btn--ghost" @click="openBatch(batch)">重试</button></p>
      <p v-else-if="!races.length">该批次没有比赛。</p>
      <div v-else class="race-buttons"><button v-for="item in races" :key="item.id" class="ui-btn ui-btn--ghost" :class="{ selected: race?.id === item.id }" :disabled="busy" @click="openRace(item)">{{ item.date }} {{ item.name }}（{{ item.score_count }} 条）</button></div>
    </section>
    <section v-if="race" class="panel">
      <h2>{{ race.name }} · 成绩</h2>
      <p>按用户身份关联，修改得分后点击对应行的保存。</p>
      <p v-if="scoreLoading" role="status">正在加载成绩…</p>
      <p v-else-if="scoreError" role="alert">{{ scoreError }} <button class="ui-btn ui-btn--ghost" @click="openRace(race)">重新加载</button></p>
      <p v-else-if="!scores.length">该比赛没有成绩。</p>
      <div v-else class="table-wrap"><table><thead><tr><th>用户名</th><th>QQ 号</th><th>得分</th><th>操作</th></tr></thead>
        <tbody><tr v-for="score in scores" :key="score.id"><td>{{ score.username }}</td><td>{{ score.qq }}</td><td><input v-model="score.draft" type="number" step="1" :aria-label="`${score.username}的得分`" :disabled="busy" /></td><td><button class="ui-btn ui-btn--primary ui-btn--sm" :disabled="busy || score.draft === '' || Number(score.draft) === score.points" @click="saveScore(score)">保存</button></td></tr></tbody>
      </table></div>
      <button class="ui-btn ui-btn--ghost ui-btn--sm" :disabled="busy" @click="openRace(race)">重新加载成绩（放弃未保存修改）</button>
    </section>
  </div>
</template>

<style scoped>
.history-page { max-width: 1080px; margin: 0 auto; padding: var(--spacing-5) var(--spacing-4); }
.panel { margin-bottom: var(--spacing-5); padding: var(--spacing-4); border: 1px solid var(--color-border-hairline); border-radius: var(--rounded-lg); background: var(--color-surface-raised); }
h2 { font-size: 20px; margin: 0 0 var(--spacing-3); }
h3 { font-size: 16px; overflow-wrap: anywhere; margin: var(--spacing-4) 0; }
p { margin: var(--spacing-3) 0; line-height: 1.6; }
.table-wrap { overflow-x: auto; margin: var(--spacing-3) 0; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: var(--spacing-3) var(--spacing-2); border-bottom: 1px solid var(--color-border-hairline); }
th { color: var(--color-ink-secondary); white-space: nowrap; }
td { min-width: 80px; }
input[type=number] { width: 100px; border: 1px solid var(--color-border-strong); border-radius: var(--rounded-md); padding: 8px; background: var(--color-surface-base); color: var(--color-ink-primary); }
.upload-box { display: flex; flex-wrap: wrap; align-items: center; gap: var(--spacing-4); border: 1px dashed var(--color-border-strong); background: var(--color-surface-base); border-radius: var(--rounded-lg); padding: var(--spacing-4); }
.file-input { display: none; }
.import-options { display: flex; flex-wrap: wrap; gap: 12px 24px; border: 1px solid var(--color-border-hairline); border-radius: var(--rounded-md); padding: var(--spacing-3); margin: var(--spacing-4) 0; }
.import-options legend { font-size: 14px; font-weight: 600; padding: 0 6px; }
.import-options label { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; min-height: 32px; }
.import-options input { width: 16px; height: 16px; accent-color: var(--color-primary); }
.import-options p { flex-basis: 100%; margin: 0; font-size: 13px; color: var(--color-ink-secondary); }
.file-button { gap: 8px; min-height: 44px; }
.file-button svg { width: 20px; height: 20px; }
.file-description { display: grid; gap: 4px; min-width: 0; flex: 1 1 220px; }
.file-description strong { overflow-wrap: anywhere; font-size: 14px; }
.file-description span, .diff-help, .diff-date { font-size: 13px; color: var(--color-ink-secondary); }
.diff-card { border: 1px solid var(--color-border-strong); border-radius: var(--rounded-md); padding: var(--spacing-4); margin: var(--spacing-4) 0; }
.diff-card h3 { margin-top: 0; }
.preview-summary, .diff-card .table-wrap { max-height: 360px; }
.preview-summary thead th, .diff-card thead th { position: sticky; top: 0; z-index: 1; background: var(--color-surface-base); }
.diff-date { margin-left: 8px; font-weight: 400; }
.diff-old { background: var(--color-destructive-tint); }
.diff-new { background: var(--color-primary-tint); }
.diff-choices { display: flex; gap: 10px; flex-wrap: wrap; border: 0; padding: 0; margin-top: var(--spacing-3); }
.diff-choices legend { font-weight: 600; margin-bottom: 8px; }
.diff-choices label { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border: 1px solid var(--color-border-strong); border-radius: var(--rounded-md); cursor: pointer; }
.diff-choices label.chosen { border-color: var(--color-primary); background: var(--color-primary-tint); }
.diff-choices input { accent-color: var(--color-primary); }
.pending { color: var(--color-destructive); font-weight: 600; }
.batch-updates { display: block; color: var(--color-ink-secondary); font-size: 12px; margin-top: 4px; }
.actions, .race-buttons { display: flex; flex-wrap: wrap; gap: var(--spacing-2); margin-top: var(--spacing-3); }
.race-buttons .selected { box-shadow: inset 0 0 0 2px var(--color-primary); }
.error, .danger { color: var(--color-destructive); }
.notice { color: var(--color-primary); }
.undo-confirm { padding: var(--spacing-3); border: 1px solid var(--color-destructive); border-radius: var(--rounded-md); }
</style>
