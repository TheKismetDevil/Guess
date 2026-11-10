<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import axios from 'axios'
import {
  previewHistory,
  importHistory,
  getHistoryBatches,
  getBatchRaces,
  getHistoryScores,
  saveHistoryScore,
  undoHistoryBatch,
} from '@/api/historical'
import type {
  ImportPreview,
  ImportBatch,
  HistoryRace,
  HistoryScore,
  ImportDifference,
  ImportDecision,
  HistoryImportOptions,
} from '@/types/historical'

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
const replacementCount = computed(
  () => Object.values(decisions.value).filter(d => d === 'replace').length + (preview.value?.reimported_races ?? 0),
)
const totalImportedRaces = computed(() => batches.value.reduce((sum, item) => sum + item.race_count, 0))
const totalImportedScores = computed(() => batches.value.reduce((sum, item) => sum + item.score_count, 0))

const fieldLabels: Record<string, string> = {
  age_range: '年龄范围',
  sex_restriction: '性别限定',
  race_grade: '比赛等级',
  country: '国家或地区',
  surface: '场地',
  distance: '距离（米）',
  horse_count: '参赛马匹数',
}

function diffLabel(diff: ImportDifference) {
  return diff.kind === 'metadata' ? fieldLabels[diff.field] ?? diff.field : `QQ ${diff.qq}`
}

function diffValue(diff: ImportDifference, side: 'before' | 'after') {
  if (diff.kind === 'metadata') return String(diff[side])
  const score = diff[side]
  return score ? `${score.points} 分` : '无成绩（未参与）'
}

function previewActionText(item: ImportPreview['races'][number]): string {
  if (item.action === 'import') return '新增'
  if (item.action === 'conflict') return '存在差异，请在下方选择'
  if (item.action === 'reimport') return '内容相同，重新导入'
  return `跳过：${item.reason}`
}

function previewActionClass(action: ImportPreview['races'][number]['action']): string {
  if (action === 'import') return 'status-unused'
  if (action === 'reimport') return 'status-placeholder'
  if (action === 'conflict') return 'status-conflict'
  return 'status-used'
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
  if (file.size > 10 * 1024 * 1024) {
    error.value = '文件不能超过 10 MB'
    return
  }
  busy.value = true
  try {
    const bytes = await file.arrayBuffer()
    preview.value = await previewHistory(bytes, importOptions.value)
    content.value = bytes
  } catch (err) {
    error.value = errorText(err)
  } finally {
    busy.value = false
  }
}

async function refreshPreview() {
  if (!content.value || busy.value) return
  preview.value = null
  decisions.value = {}
  error.value = ''
  message.value = ''
  busy.value = true
  try {
    preview.value = await previewHistory(content.value, importOptions.value)
  } catch (err) {
    error.value = errorText(err)
  } finally {
    busy.value = false
  }
}

async function confirmImport() {
  if (!preview.value || !content.value || busy.value) return
  if (unresolved.value) {
    error.value = '请先为每场有差异的比赛作出选择'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const result = await importHistory(
      content.value,
      filename.value,
      preview.value.preview_token,
      decisions.value,
      importOptions.value,
    )
    message.value =
      `新增 ${result.imported_races} 场比赛、${result.imported_scores} 条成绩；更新 ${result.updated_races} 场；保留或跳过 ${result.skipped_races.length} 场。` +
      (result.placeholder_users ? `已为 ${result.placeholder_users} 个未注册 QQ 创建占位用户和邀请码。` : '')
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
  } finally {
    busy.value = false
  }
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
  } catch (err) {
    if (request === detailRequest) detailError.value = errorText(err)
  } finally {
    if (request === detailRequest) detailLoading.value = false
  }
}

function closeBatch() {
  ++detailRequest
  ++scoreRequest
  batch.value = null
  race.value = null
  races.value = []
  scores.value = []
  detailError.value = ''
  scoreError.value = ''
  detailLoading.value = false
  scoreLoading.value = false
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
  } catch (err) {
    if (request === scoreRequest) scoreError.value = errorText(err)
  } finally {
    if (request === scoreRequest) scoreLoading.value = false
  }
}

async function saveScore(score: HistoryScore & { draft: number | string }) {
  const points = score.draft === '' ? NaN : Number(score.draft)
  if (!Number.isInteger(points) || points < -2147483648 || points > 2147483647) {
    error.value = '得分必须是有效整数，未参与比赛请留在原始工作簿中为空。'
    return
  }
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const saved = await saveHistoryScore(score.id, points, score.points)
    Object.assign(score, saved, { draft: saved.points })
    message.value = '成绩已保存，排行榜将按最新成绩计算。'
  } catch (err) {
    error.value = errorText(err)
  } finally {
    busy.value = false
  }
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
    closeBatch()
    message.value = '已删除该导入批次并回滚对应历史成绩，排行榜已重新计算。'
    await loadBatches()
  } catch (err) {
    error.value = errorText(err)
  } finally {
    busy.value = false
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && undoTarget.value && !busy.value) {
    undoTarget.value = null
  }
}

onMounted(() => {
  loadBatches()
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="history-page">
    <header class="ui-page-header">
      <div>
        <span class="ui-page-eyebrow">Admin</span>
        <h1 class="ui-page-title">历史成绩管理</h1>
        <p class="ui-page-subtitle">预览导入工作簿、核对差异批次与修正选手历史得分，变更实时同步至排行榜。</p>
      </div>
      <router-link to="/leaderboard" class="ui-btn ui-btn--ghost ui-btn--sm">
        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5C7 4 6 7 6 9z" />
          <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5C17 4 18 7 18 9z" />
          <path d="M4 22h16" />
          <path d="M10 22V14h4v8" />
          <path d="M12 14c-1.5 0-3-2-3-4V7c0-1.1.9-2 2-2h2a2 2 0 0 1 2 2v3c0 2-1.5 4-3 4z" />
        </svg>
        查看排行榜
      </router-link>
    </header>

    <Transition name="ui-fade">
      <p v-if="error" role="alert" class="ui-banner ui-banner--error">{{ error }}</p>
    </Transition>
    <Transition name="ui-fade">
      <p v-if="message" role="status" class="ui-banner ui-banner--success">{{ message }}</p>
    </Transition>

    <!-- Import Card -->
    <section class="section-card">
      <div class="section-header">
        <div>
          <h2 class="section-title">导入历史成绩</h2>
          <p class="section-subtitle">
            选择包含“历史得分”和“赛事资料”的 Excel（最多 10 MB）。QQ 号用于关联用户；0 分计入参与场次，空白表示未参与。
          </p>
        </div>
      </div>

      <fieldset class="field-box import-options" :disabled="busy">
        <legend class="field-box-header">导入选项</legend>
        <div class="options-row">
          <label class="option-check">
            <input v-model="importOptions.skip_identical" type="checkbox" @change="refreshPreview" />
            <span>跳过完全相同的比赛记录</span>
          </label>
          <label class="option-check">
            <input v-model="importOptions.skip_empty" type="checkbox" @change="refreshPreview" />
            <span>不导入无成绩的比赛</span>
          </label>
        </div>
        <p class="field-box-hint">
          两个选项默认勾选，修改后会重新预览并清除差异选择。0 分仍是一条有效成绩；全部成绩为空才属于无成绩比赛。
        </p>
      </fieldset>

      <div class="upload-box">
        <input
          ref="fileInput"
          class="file-input"
          type="file"
          accept=".xlsx"
          tabindex="-1"
          aria-label="选择历史成绩 Excel 文件"
          :disabled="busy"
          @change="selectFile"
        />
        <button type="button" class="ui-btn ui-btn--primary file-button" :disabled="busy" @click="fileInput?.click()">
          <span v-if="busy" class="ui-spinner" aria-hidden="true"></span>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 16V4m-4 4 4-4 4 4M4 16v4h16v-4" />
          </svg>
          {{ busy ? '正在处理…' : filename ? '重新选择 Excel' : '选择 Excel 文件' }}
        </button>
        <div class="file-description">
          <strong>{{ filename || '上传历史成绩工作簿' }}</strong>
          <span>支持 .xlsx · 最大 10 MB · 选择后先预览差异</span>
        </div>
      </div>

      <p v-if="busy" role="status" class="busy-hint">
        <span class="ui-spinner" aria-hidden="true"></span>
        正在处理，请稍候…
      </p>

      <div v-if="preview" class="preview-block">
        <div class="preview-header">
          <h3 class="preview-filename">{{ filename }}</h3>
          <p class="preview-stats">
            {{ preview.participants }} 位参与者 · 新增 {{ preview.imported_races }} 场 / {{ preview.imported_scores }} 条成绩 · 重新导入 {{ preview.reimported_races }} 场 · 待核对 {{ preview.conflicting_races }} 场 · 跳过 {{ preview.skipped_races.length }} 场
          </p>
        </div>

        <div class="table-wrapper preview-summary">
          <table class="admin-table preview-table">
            <thead>
              <tr>
                <th scope="col">比赛</th>
                <th scope="col">日期</th>
                <th scope="col">成绩数</th>
                <th scope="col">处理方式</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in preview.races" :key="item.name">
                <td class="cell-primary">{{ item.name }}</td>
                <td data-label="日期"><span class="cell-date">{{ item.date }}</span></td>
                <td data-label="成绩数"><span class="num-text">{{ item.score_count }}</span></td>
                <td data-label="处理方式">
                  <span class="status-chip" :class="previewActionClass(item.action)">
                    {{ previewActionText(item) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <section v-for="item in conflicts" :key="item.race_id!" class="diff-card">
          <div class="diff-card-header">
            <h3>
              {{ item.name }}
              <span class="diff-date">{{ item.date }}</span>
            </h3>
            <span
              class="status-chip"
              :class="decisions[String(item.race_id)] ? 'status-unused' : 'status-conflict'"
            >
              {{ decisions[String(item.race_id)] ? '已选择' : '待核对' }}
            </span>
          </div>

          <div class="table-wrapper diff-table-wrap">
            <table class="admin-table diff-table">
              <thead>
                <tr>
                  <th scope="col">差异项</th>
                  <th scope="col">已有内容</th>
                  <th scope="col">本次文件</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(diff, index) in item.differences" :key="index">
                  <th scope="row" class="diff-field">{{ diffLabel(diff) }}</th>
                  <td data-label="已有内容" class="diff-old">{{ diffValue(diff, 'before') }}</td>
                  <td data-label="本次文件" class="diff-new">{{ diffValue(diff, 'after') }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <fieldset :disabled="busy" class="diff-choices">
            <legend>这场比赛如何处理？</legend>
            <label :class="{ chosen: decisions[String(item.race_id)] === 'keep' }">
              <input v-model="decisions[String(item.race_id)]" type="radio" :name="`decision-${item.race_id}`" value="keep" />
              保留已有内容
            </label>
            <label :class="{ chosen: decisions[String(item.race_id)] === 'replace' }">
              <input v-model="decisions[String(item.race_id)]" type="radio" :name="`decision-${item.race_id}`" value="replace" />
              使用本次文件
            </label>
          </fieldset>
          <p class="diff-help">
            选择“使用本次文件”会替换这场比赛的赛事资料和全部历史成绩。文件中为空或缺少的用户成绩会被移除；选择“保留已有”则维持整场比赛的原数据。
          </p>
        </section>

        <p v-if="unresolved" role="status" class="pending">还有 {{ unresolved }} 场差异未选择。</p>

        <div class="actions">
          <button
            type="button"
            class="ui-btn ui-btn--primary"
            :disabled="busy || unresolved > 0 || (!preview.imported_races && !conflicts.length && !preview.reimported_races)"
            @click="confirmImport"
          >
            <span v-if="busy" class="ui-spinner" aria-hidden="true"></span>
            确认处理（新增 {{ preview.imported_races }} 场 / 更新 {{ replacementCount }} 场）
          </button>
          <button
            type="button"
            class="ui-btn ui-btn--ghost"
            :disabled="busy"
            @click="preview = null; content = null; decisions = {}"
          >
            取消
          </button>
        </div>
      </div>
    </section>

    <!-- Batches Section -->
    <section class="batches-section">
      <div class="section-toolbar">
        <h2 class="section-title">导入批次</h2>
        <span v-if="pageState === 'success'" class="summary">
          共 <strong>{{ batches.length }}</strong> 个批次，累计导入 {{ totalImportedRaces }} 场比赛 · {{ totalImportedScores }} 条成绩
        </span>
      </div>

      <div v-if="pageState === 'loading'" class="skeleton-container" role="status" aria-live="polite" aria-label="正在加载批次…">
        <div v-for="i in 4" :key="i" class="ui-skeleton skeleton-row"></div>
      </div>

      <div v-else-if="pageState === 'empty'" class="ui-state empty-state" role="status" aria-live="polite">
        <span class="ui-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="8" y1="13" x2="16" y2="13" />
            <line x1="8" y1="17" x2="16" y2="17" />
          </svg>
        </span>
        <p class="ui-state-text">暂无历史成绩，请先选择 Excel 预览。</p>
      </div>

      <div v-else-if="pageState === 'error'" class="ui-state ui-state--error" role="alert" aria-live="polite">
        <span class="ui-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </span>
        <p class="ui-state-text">加载历史导入批次失败</p>
        <button type="button" class="ui-btn ui-btn--primary" @click="loadBatches">加载失败，点击重试</button>
      </div>

      <div v-else class="table-wrapper">
        <table class="admin-table batch-table">
          <thead>
            <tr>
              <th scope="col">文件 / 批次</th>
              <th scope="col">导入时间</th>
              <th scope="col">比赛 / 成绩</th>
              <th scope="col" class="col-actions"><span class="sr-only">操作</span></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in batches"
              :key="item.id"
              :class="{ 'is-active': batch?.id === item.id }"
            >
              <td class="cell-primary">
                <div class="batch-name-wrap">
                  <span class="batch-id-chip">#{{ item.id }}</span>
                  <span class="batch-filename">{{ item.filename }}</span>
                </div>
              </td>
              <td data-label="导入时间">
                <span class="cell-date">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</span>
              </td>
              <td data-label="比赛 / 成绩">
                <span class="num-text">{{ item.race_count }} / {{ item.score_count }}</span>
                <span v-if="item.updated_races" class="status-chip status-placeholder batch-updates">
                  另更新 {{ item.updated_races }} 场
                </span>
              </td>
              <td class="col-actions">
                <div class="row-actions">
                  <button
                    type="button"
                    class="row-btn"
                    :class="{ 'is-active': batch?.id === item.id }"
                    :title="`查看「${item.filename}」成绩`"
                    :disabled="busy"
                    @click="openBatch(item)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                    <span class="row-btn-label">查看成绩</span>
                  </button>
                  <button
                    type="button"
                    class="row-btn row-btn-danger"
                    :title="`撤销「${item.filename}」`"
                    :disabled="busy"
                    @click="undoTarget = item"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                      <path d="M10 11v6" />
                      <path d="M14 11v6" />
                    </svg>
                    <span class="row-btn-label">撤销批次</span>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Undo Confirmation Modal -->
      <div
        v-if="undoTarget"
        class="modal-overlay ui-anim-overlay"
        role="dialog"
        aria-modal="true"
        aria-labelledby="undo-batch-title"
        @click.self="!busy && (undoTarget = null)"
      >
        <div class="modal-content ui-anim-dialog undo-confirm" role="alert">
          <h2 id="undo-batch-title" class="modal-title">撤销导入批次</h2>
          <p class="modal-message">
            确认撤销「{{ undoTarget.filename }}」？将删除该导入批次记录，移除新增的 {{ undoTarget.race_count }} 场比赛、{{ undoTarget.score_count }} 条成绩，并恢复 {{ undoTarget.updated_races }} 场更新前的数据。若存在后续导入更新或更新后的人工修分，会提示冲突并停止撤销。请保留原始 Excel。
          </p>
          <div class="modal-actions">
            <button type="button" class="ui-btn ui-btn--ghost" :disabled="busy" @click="undoTarget = null">取消</button>
            <button type="button" class="ui-btn ui-btn--danger-solid" :disabled="busy" @click="confirmUndo">
              <span v-if="busy" class="ui-spinner" aria-hidden="true"></span>
              确认撤销
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- Batch Races Card -->
    <section v-if="batch" class="section-card">
      <div class="section-header">
        <div>
          <span class="section-eyebrow">批次 #{{ batch.id }}</span>
          <h2 class="section-title">{{ batch.filename }} · 比赛</h2>
        </div>
        <button type="button" class="ui-btn ui-btn--ghost ui-btn--sm" :disabled="busy" @click="closeBatch">
          收起
        </button>
      </div>

      <div v-if="detailLoading" class="skeleton-container" role="status" aria-label="正在加载比赛…">
        <div v-for="i in 3" :key="i" class="ui-skeleton skeleton-row"></div>
      </div>
      <div v-else-if="detailError" class="inline-error" role="alert">
        <span>{{ detailError }}</span>
        <button type="button" class="ui-btn ui-btn--ghost ui-btn--sm" @click="openBatch(batch)">重试</button>
      </div>
      <p v-else-if="!races.length" class="empty-inline">该批次没有比赛。</p>
      <div v-else class="race-buttons">
        <button
          v-for="item in races"
          :key="item.id"
          type="button"
          class="ui-btn ui-btn--ghost race-pill-btn"
          :class="{ selected: race?.id === item.id }"
          :disabled="busy"
          @click="openRace(item)"
        >
          <span class="race-pill-date">{{ item.date }}</span>
          <span class="race-pill-name">{{ item.name }}</span>
          <span class="race-pill-count">（{{ item.score_count }} 条）</span>
        </button>
      </div>
    </section>

    <!-- Race Scores Card -->
    <section v-if="race" class="section-card">
      <div class="section-header">
        <div>
          <span class="section-eyebrow">{{ race.date }}</span>
          <h2 class="section-title">{{ race.name }} · 成绩</h2>
          <p class="section-subtitle">按用户身份关联，修改得分后点击对应行的保存。</p>
        </div>
        <button type="button" class="ui-btn ui-btn--ghost ui-btn--sm" :disabled="busy" @click="openRace(race)">
          重新加载成绩（放弃未保存修改）
        </button>
      </div>

      <div v-if="scoreLoading" class="skeleton-container" role="status" aria-label="正在加载成绩…">
        <div v-for="i in 4" :key="i" class="ui-skeleton skeleton-row"></div>
      </div>
      <div v-else-if="scoreError" class="inline-error" role="alert">
        <span>{{ scoreError }}</span>
        <button type="button" class="ui-btn ui-btn--ghost ui-btn--sm" @click="openRace(race)">重新加载</button>
      </div>
      <p v-else-if="!scores.length" class="empty-inline">该比赛没有成绩。</p>
      <div v-else class="table-wrapper">
        <table class="admin-table score-table">
          <thead>
            <tr>
              <th scope="col">用户名</th>
              <th scope="col">QQ 号</th>
              <th scope="col">得分</th>
              <th scope="col" class="col-actions"><span class="sr-only">操作</span></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="score in scores"
              :key="score.id"
              :class="{ 'is-dirty': score.draft !== '' && Number(score.draft) !== score.points }"
            >
              <td class="cell-primary">
                <span class="score-username">{{ score.username }}</span>
                <span
                  v-if="score.draft !== '' && Number(score.draft) !== score.points"
                  class="status-chip status-placeholder dirty-chip"
                >
                  待保存
                </span>
              </td>
              <td data-label="QQ 号">
                <code class="qq-code">{{ score.qq }}</code>
              </td>
              <td data-label="得分">
                <input
                  v-model="score.draft"
                  type="number"
                  step="1"
                  class="ui-input score-input"
                  :aria-label="`${score.username}的得分`"
                  :disabled="busy"
                />
              </td>
              <td class="col-actions">
                <div class="row-actions">
                  <button
                    type="button"
                    class="ui-btn ui-btn--primary ui-btn--sm"
                    :disabled="busy || score.draft === '' || Number(score.draft) === score.points"
                    @click="saveScore(score)"
                  >
                    保存
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.history-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--spacing-5) var(--spacing-4);
}

.btn-icon {
  width: 16px;
  height: 16px;
}

/* =========================================
   Section Cards & Headers
   ========================================= */

.section-card {
  margin-bottom: var(--spacing-5);
  padding: var(--spacing-5);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-sm);
  animation: rise-in var(--duration-slow) var(--ease-out) backwards;
}

.batches-section {
  margin-bottom: var(--spacing-5);
}

.section-header,
.section-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
}

.section-toolbar {
  margin-bottom: var(--spacing-3);
}

.section-eyebrow {
  display: inline-block;
  font-family: var(--font-display);
  font-size: var(--text-caption);
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--color-primary);
  margin-bottom: 2px;
}

.section-title {
  font-family: var(--font-display);
  font-size: var(--text-heading);
  font-weight: 700;
  line-height: 1.2;
  color: var(--color-ink-primary);
  margin: 0;
}

.section-subtitle {
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
  margin: var(--spacing-1) 0 0;
  line-height: 1.6;
}

.summary {
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
}

.summary strong {
  color: var(--color-primary);
}

/* =========================================
   Import Controls & Field Box
   ========================================= */

.field-box {
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-md);
  background: var(--color-surface-base);
  padding: var(--spacing-3) var(--spacing-4);
  margin: 0 0 var(--spacing-4);
}

.field-box-header {
  padding: 0 6px;
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-ink-secondary);
}

.options-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2) var(--spacing-6);
  margin-top: var(--spacing-1);
}

.option-check {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  min-height: 32px;
  font-size: var(--text-body-sm);
  font-weight: 500;
  color: var(--color-ink-primary);
  cursor: pointer;
}

.option-check input {
  width: 16px;
  height: 16px;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.field-box-hint {
  margin: var(--spacing-2) 0 0;
  font-size: var(--text-caption);
  color: var(--color-ink-secondary);
  line-height: 1.5;
}

.upload-box {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-4);
  padding: var(--spacing-4);
  border: 1.5px dashed var(--color-border-strong);
  border-radius: var(--rounded-lg);
  background: var(--color-surface-base);
  transition: border-color var(--duration-fast) ease, background-color var(--duration-fast) ease;
}

.upload-box:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-tint);
}

.file-input {
  display: none;
}

.file-button {
  gap: var(--spacing-2);
  min-height: 44px;
}

.file-button svg {
  width: 18px;
  height: 18px;
}

.file-description {
  display: grid;
  gap: 2px;
  min-width: 0;
  flex: 1 1 220px;
}

.file-description strong {
  overflow-wrap: anywhere;
  font-size: var(--text-body-sm);
  color: var(--color-ink-primary);
}

.file-description span,
.diff-help,
.diff-date {
  font-size: var(--text-caption);
  color: var(--color-ink-secondary);
}

.busy-hint {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  margin: var(--spacing-3) 0 0;
  font-size: var(--text-body-sm);
  color: var(--color-primary);
}

/* =========================================
   Preview & Conflict Diffs
   ========================================= */

.preview-block {
  margin-top: var(--spacing-5);
  padding-top: var(--spacing-4);
  border-top: 1px solid var(--color-border-hairline);
}

.preview-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--spacing-2) var(--spacing-4);
  margin-bottom: var(--spacing-3);
}

.preview-filename {
  font-family: var(--font-display);
  font-size: var(--text-subheading);
  font-weight: 700;
  color: var(--color-ink-primary);
  overflow-wrap: anywhere;
  margin: 0;
}

.preview-stats {
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
  margin: 0;
}

.preview-summary,
.diff-table-wrap {
  max-height: 360px;
  overflow-y: auto;
}

.preview-summary thead th,
.diff-table-wrap thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--color-surface-base);
}

.diff-card {
  margin: var(--spacing-4) 0;
  padding: var(--spacing-4);
  background: var(--color-surface-base);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--rounded-lg);
}

.diff-card-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-2);
  margin-bottom: var(--spacing-3);
}

.diff-card-header h3 {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-ink-primary);
  margin: 0;
}

.diff-date {
  margin-left: var(--spacing-2);
  font-family: var(--font-display);
  font-weight: 500;
}

.diff-field {
  font-weight: 600;
  color: var(--color-ink-primary);
}

.diff-old {
  background: var(--color-destructive-tint);
  color: var(--color-destructive-dark);
}

.diff-new {
  background: var(--color-primary-tint);
  color: var(--color-primary-dark);
  font-weight: 600;
}

.diff-choices {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
  border: 0;
  padding: 0;
  margin-top: var(--spacing-3);
}

.diff-choices legend {
  width: 100%;
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-ink-primary);
  margin-bottom: var(--spacing-2);
}

.diff-choices label {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: 8px 14px;
  font-size: var(--text-body-sm);
  font-weight: 500;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--rounded-md);
  cursor: pointer;
  transition: border-color var(--duration-fast) ease, background-color var(--duration-fast) ease;
}

.diff-choices label:hover {
  border-color: var(--color-primary);
}

.diff-choices label.chosen {
  border-color: var(--color-primary);
  background: var(--color-primary-tint);
  color: var(--color-primary-dark);
  font-weight: 600;
}

.diff-choices input {
  accent-color: var(--color-primary);
}

.diff-help {
  margin: var(--spacing-2) 0 0;
  line-height: 1.5;
}

.pending {
  margin: var(--spacing-3) 0;
  padding: var(--spacing-2) var(--spacing-3);
  border-radius: var(--rounded-md);
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-destructive);
  background: var(--color-destructive-tint);
  border: 1px solid var(--color-destructive-light);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-3);
  margin-top: var(--spacing-4);
}

/* =========================================
   Shared Admin Table & Status Chips
   ========================================= */

.table-wrapper {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-sm);
  animation: rise-in var(--duration-slow) var(--ease-out) backwards;
}

.admin-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-body-sm);
}

.admin-table thead tr {
  background: var(--color-surface-base);
}

.admin-table th {
  padding: var(--spacing-3);
  font-size: var(--text-caption);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-align: left;
  white-space: nowrap;
  color: var(--color-ink-secondary);
  border-bottom: 1px solid var(--color-border-hairline);
}

.admin-table td {
  padding: var(--spacing-3);
  vertical-align: middle;
  white-space: nowrap;
  border-bottom: 1px solid var(--color-border-hairline);
}

.admin-table tbody tr {
  transition: background var(--duration-fast) ease;
}

.admin-table tbody tr:hover {
  background: var(--color-primary-tint);
}

.admin-table tbody tr.is-active {
  background: var(--color-primary-tint);
}

.admin-table tbody tr.is-dirty {
  background: var(--color-accent-tint);
}

.admin-table tbody tr:last-child td,
.admin-table tbody tr:last-child th {
  border-bottom: none;
}

.cell-primary {
  font-weight: 600;
  color: var(--color-ink-primary);
}

.batch-name-wrap {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
}

.batch-id-chip {
  padding: 1px 7px;
  border-radius: var(--rounded-full);
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  color: var(--color-ink-secondary);
  background: var(--color-surface-sunken);
}

.batch-filename {
  font-weight: 600;
  color: var(--color-ink-primary);
  overflow-wrap: anywhere;
  white-space: normal;
}

.cell-date {
  font-family: var(--font-display);
  font-size: 13px;
  color: var(--color-ink-secondary);
}

.num-text {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--color-ink-primary);
}

.status-chip {
  display: inline-block;
  padding: 1px 10px;
  border-radius: var(--rounded-full);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.status-unused {
  color: var(--color-primary);
  background: var(--color-primary-tint);
}

.status-used {
  color: var(--color-ink-secondary);
  background: var(--color-surface-sunken);
}

.status-placeholder {
  color: var(--color-accent-dark);
  background: var(--color-accent-tint);
}

.status-conflict {
  color: var(--color-destructive);
  background: var(--color-destructive-tint);
}

.batch-updates,
.dirty-chip {
  margin-left: var(--spacing-2);
}

.qq-code {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--rounded-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  color: var(--color-ink-secondary);
  background: var(--color-surface-sunken);
}

.score-username {
  font-weight: 600;
  color: var(--color-ink-primary);
}

.score-input {
  width: 112px;
  min-height: 36px;
  padding: 6px 10px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

/* =========================================
   Row Actions (unified with Horses & Users)
   ========================================= */

.col-actions {
  width: 1%;
  text-align: right;
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

.row-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 32px;
  padding: 0 10px;
  border-radius: var(--rounded-full);
  font-size: var(--text-caption);
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  color: var(--color-ink-secondary);
  transition:
    color var(--duration-fast) ease,
    background var(--duration-fast) ease,
    transform var(--duration-fast) var(--ease-out);
}

.row-btn svg {
  flex-shrink: 0;
  width: 15px;
  height: 15px;
}

.row-btn:hover:not(:disabled),
.row-btn.is-active {
  color: var(--color-primary);
  background: var(--color-surface-raised);
  box-shadow: inset 0 0 0 1px var(--color-primary-tint-strong);
}

.row-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.row-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.row-btn-danger:hover:not(:disabled) {
  color: var(--color-destructive);
  box-shadow: inset 0 0 0 1px var(--color-destructive-light);
}

/* =========================================
   Race Selector Pills & States
   ========================================= */

.race-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.race-pill-btn {
  min-height: 40px;
  padding: 8px 14px;
  gap: 6px;
  font-size: var(--text-body-sm);
}

.race-pill-date {
  font-family: var(--font-display);
  font-weight: 600;
  color: var(--color-ink-secondary);
}

.race-pill-name {
  font-weight: 600;
  color: var(--color-ink-primary);
}

.race-pill-count {
  font-size: var(--text-caption);
  color: var(--color-ink-secondary);
}

.race-pill-btn.selected {
  color: var(--color-primary-dark);
  background: var(--color-primary-tint);
  border-color: var(--color-primary);
  box-shadow: inset 0 0 0 1px var(--color-primary);
}

.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.skeleton-row {
  height: 52px;
  border-radius: var(--rounded-md);
}

.empty-state {
  min-height: 28vh;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
}

.inline-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  padding: var(--spacing-3);
  border-radius: var(--rounded-md);
  color: var(--color-destructive);
  background: var(--color-destructive-tint);
  border: 1px solid var(--color-destructive-light);
}

.empty-inline {
  margin: 0;
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
}

/* =========================================
   Modal (Undo Confirmation)
   ========================================= */

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(13, 30, 18, 0.5);
  padding: var(--spacing-4);
}

.modal-content {
  background: var(--color-surface-raised);
  border-radius: var(--rounded-xl);
  padding: var(--spacing-6);
  max-width: 440px;
  width: 100%;
}

.modal-title {
  font-family: var(--font-display);
  font-size: var(--text-heading);
  font-weight: 700;
  color: var(--color-ink-primary);
  margin: 0 0 var(--spacing-3);
}

.modal-message {
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
  line-height: 1.65;
  margin: 0 0 var(--spacing-6);
}

.modal-actions {
  display: flex;
  gap: var(--spacing-3);
  justify-content: flex-end;
}

/* =========================================
   Mobile (<768px): Table Rows Become Cards
   ========================================= */

@media (max-width: 767px) {
  .section-card {
    padding: var(--spacing-4);
  }

  .batch-table thead,
  .score-table thead {
    display: none;
  }

  .batch-table,
  .batch-table tbody,
  .batch-table tr,
  .batch-table td,
  .score-table,
  .score-table tbody,
  .score-table tr,
  .score-table td {
    display: block;
  }

  .batch-table tbody,
  .score-table tbody {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .batches-section .table-wrapper,
  .section-card > .table-wrapper {
    overflow: visible;
    background: transparent;
    border: none;
    box-shadow: none;
  }

  .batch-table tr,
  .score-table tr {
    position: relative;
    padding: var(--spacing-3) var(--spacing-4);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border-hairline);
    border-radius: var(--rounded-lg);
    box-shadow: var(--shadow-sm);
  }

  .batch-table tbody tr:hover,
  .score-table tbody tr:hover {
    background: var(--color-surface-raised);
  }

  .batch-table tbody tr.is-active {
    background: var(--color-primary-tint);
    border-color: var(--color-primary);
  }

  .score-table tbody tr.is-dirty {
    background: var(--color-accent-tint);
  }

  .batch-table td,
  .score-table td {
    padding: 3px 0;
    border: none;
    white-space: normal;
  }

  .batch-table td[data-label],
  .score-table td[data-label] {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    font-size: 13px;
  }

  .batch-table td[data-label]::before,
  .score-table td[data-label]::before {
    content: attr(data-label);
    flex: 0 0 5.5em;
    font-size: 11px;
    font-weight: 600;
    color: var(--color-ink-disabled);
  }

  .batch-table .cell-primary,
  .score-table .cell-primary {
    padding-right: 92px;
    margin-bottom: 4px;
  }

  .batch-table .col-actions,
  .score-table .col-actions {
    position: absolute;
    top: var(--spacing-3);
    right: var(--spacing-3);
    width: auto;
    padding: 0;
  }

  .batch-table .row-btn {
    width: 36px;
    height: 36px;
    padding: 0;
    justify-content: center;
    background: var(--color-surface-base);
  }

  .batch-table .row-btn-label {
    display: none;
  }
}
</style>
