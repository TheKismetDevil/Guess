import assert from 'node:assert/strict'
import { after, before, beforeEach, test } from 'node:test'
import axios from 'axios'
import { createServer } from 'vite'
import { createSSRApp, createRenderer, ref, nextTick } from 'vue'
import { renderToString } from 'vue/server-renderer'

let server
let apiClient
let useVote
let useHeadToHead
let LeaderboardRow
let getLeaderboard
let LeaderboardSortSelect
let requests
let respond
const originalAdapter = axios.defaults.adapter
const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
const originalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')

before(async () => {
  axios.defaults.adapter = async config => {
    requests.push(config)
    return respond(config)
  }
  server = await createServer({
    server: { middlewareMode: true, hmr: false },
    optimizeDeps: { noDiscovery: true, include: [] },
    appType: 'custom',
  })
  apiClient = (await server.ssrLoadModule('/src/api/client.ts')).default
  useVote = (await server.ssrLoadModule('/src/composables/useVote.ts')).useVote
  useHeadToHead = (await server.ssrLoadModule('/src/composables/useHeadToHead.ts')).useHeadToHead
  LeaderboardRow = (await server.ssrLoadModule('/src/components/LeaderboardRow.vue')).default
  getLeaderboard = (await server.ssrLoadModule('/src/api/leaderboard.ts')).getLeaderboard
  LeaderboardSortSelect = (await server.ssrLoadModule('/src/components/LeaderboardSortSelect.vue')).default
})

beforeEach(() => {
  requests = []
  const storage = new Map()
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key),
  } })
  Object.defineProperty(globalThis, 'window', { configurable: true, value: {
    location: { pathname: '/races/1', search: '', href: '' },
  } })
})

after(async () => {
  await server?.close()
  axios.defaults.adapter = originalAdapter
  for (const [key, descriptor] of [['window', originalWindow], ['localStorage', originalStorage]]) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor)
    else delete globalThis[key]
  }
})

function response(config, data) {
  return { config, status: 200, statusText: 'OK', headers: {}, data }
}

function rejectRequest(config, status, message, code) {
  throw new axios.AxiosError(message, 'ERR_BAD_REQUEST', config, null, {
    config, status, statusText: 'Error', headers: {},
    data: { detail: { message, code } },
  })
}

async function createVote() {
  let vote
  await renderToString(createSSRApp({
    setup() {
      vote = useVote()
      return () => null
    },
  }))
  return vote
}

const horse = id => ({ race_horse_id: id, snapshot_data: { name: `马${id}` } })

async function renderSortSelect({ expanded = false, value = 'total_points' } = {}) {
  let controls
  const events = []
  const app = createSSRApp(LeaderboardSortSelect, {
    modelValue: value,
    'onUpdate:modelValue': next => events.push(['model', next]),
    onChange: () => events.push(['change']),
  })
  app.mixin({ created() {
    if (this.$options.__name === 'LeaderboardSortSelect') {
      controls = this.$.setupState
      if (expanded) controls.openMenu()
    }
  } })
  const html = await renderToString(app)
  return { html, controls, events }
}

function keyEvent(key) {
  return { key, preventDefault() {} }
}

test('sort dropdown renders an HTML listbox instead of the native select menu', async () => {
  const closed = await renderSortSelect()
  assert.match(closed.html, /role="combobox"/)
  assert.match(closed.html, /aria-expanded="false"/)
  assert.doesNotMatch(closed.html, /<select\b/)
  const expanded = await renderSortSelect({ expanded: true, value: 'avg_points' })
  assert.match(expanded.html, /aria-expanded="true"/)
  assert.match(expanded.html, /role="listbox"/)
  assert.equal((expanded.html.match(/role="option"/g) ?? []).length, 2)
  const selectedClass = expanded.html.match(/aria-selected="true"[^>]*class="([^"]+)"/)[1].split(' ')
  assert.ok(['sort-option', 'selected', 'active'].every(token => selectedClass.includes(token)))
  assert.match(expanded.html, /class="sort-check"/)
})

test('sort dropdown supports keyboard navigation, cancellation and one change event', async () => {
  const { controls, events } = await renderSortSelect()
  controls.onKeydown(keyEvent('ArrowDown'))
  assert.equal(controls.open, true)
  controls.onKeydown(keyEvent('ArrowDown'))
  assert.equal(controls.activeIndex, 1)
  controls.onKeydown(keyEvent('Escape'))
  assert.equal(controls.open, false)
  assert.deepEqual(events, [])
  controls.onKeydown(keyEvent('End'))
  controls.onKeydown(keyEvent('Enter'))
  assert.equal(controls.open, false)
  assert.deepEqual(events, [['model', 'avg_points'], ['change']])
})

test('sort dropdown pointer selection, outside dismissal and Tab preserve expected selection', async () => {
  const { controls, events } = await renderSortSelect()
  controls.openMenu()
  controls.choose(0)
  assert.deepEqual(events, []) // Selecting the current value must not reload the ranking.
  controls.openMenu()
  controls.onOutsidePointer({ target: {} })
  assert.equal(controls.open, false)
  controls.openMenu()
  controls.onKeydown(keyEvent('Tab'))
  assert.equal(controls.open, false)
  controls.openMenu()
  controls.choose(1)
  assert.deepEqual(events, [['model', 'avg_points'], ['change']])
})

test('leaderboard rows display average and average gaps to three decimal places', async () => {
  for (const [average, display] of [[0.667, '0.667'], [10, '10.000'], [-0.333, '-0.333'], [0, '0.000']]) {
    const html = await renderToString(createSSRApp(LeaderboardRow, {
      entry: { username: '用户', total_points: 2, races_participated: 3, avg_points: average },
      rank: 2, isCurrentUser: false, leaderGap: 1 / 3, previousGap: 1 / 6, averageRanking: true,
    }))
    assert.ok(html.includes(`>${display}</td>`))
    assert.deepEqual([...html.matchAll(/class="col-gap"[^>]*>([^<]+)<\/td>/g)].map(m => m[1]), ['0.333', '0.167'])
  }
})

test('leaderboard sorting preserves race filters and defaults to total points', async () => {
  respond = config => response(config, { data: [] })
  await getLeaderboard({ country: ['日本'], date_from: '2026-01-01' }, 'avg_points')
  assert.equal(requests[0].params.sort_by, 'avg_points')
  assert.deepEqual(requests[0].params.country, ['日本'])
  assert.equal(requests[0].params.date_from, '2026-01-01')
  await getLeaderboard()
  assert.equal(requests[1].params.sort_by, 'total_points')
})

const comparisonPeople = ['a', 'b', 'c'].map(id => ({ id, username: id, kind: 'user' }))
function comparisonResult(ids, name = '共同比赛') {
  return { participants: ids.map(id => comparisonPeople.find(p => p.id === id)),
    races: [{ key: 'historical:1', id: null, name, date: '2026-11-06', source: 'historical', scores: ids.map((_, i) => i === 0 ? 0 : -5) }] }
}
async function createComparison(context) {
  let controller
  const filters = ref({})
  // Mount with an in-memory renderer: SSR intentionally disables reactive watchers.
  const renderer = createRenderer({
    createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
    insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
    parentNode: () => null, nextSibling: () => null,
  })
  const app = renderer.createApp({ setup() { controller = useHeadToHead(filters); return () => null } })
  app.mount({})
  context.after(() => app.unmount())
  await flushRequests()
  return { controller, filters }
}
async function flushRequests() {
  await nextTick()
  await new Promise(resolve => setImmediate(resolve))
}

test('head to head waits for two users, keeps score columns aligned and clears results when deselected', async t => {
  respond = config => response(config, { data: config.url.endsWith('/participants') ? comparisonPeople : comparisonResult(config.params.participant_id) })
  const { controller } = await createComparison(t)
  controller.selected.value = ['c']
  await flushRequests()
  assert.equal(requests.filter(r => r.url.endsWith('/head-to-head')).length, 0)
  controller.selected.value = ['c', 'a', 'b']
  await flushRequests()
  assert.equal(controller.state.value, 'success')
  assert.deepEqual(controller.result.value.participants.map(p => p.id), ['c', 'a', 'b'])
  assert.deepEqual(controller.result.value.races[0].scores, [0, -5, -5])
  assert.deepEqual(controller.totals.value, [0, -5, -5])
  controller.selected.value = ['a']
  await flushRequests()
  assert.equal(controller.state.value, 'idle')
  assert.equal(controller.result.value, null)
})

test('head to head ignores an older response after the selected users change', async t => {
  let finishOld
  respond = config => {
    if (config.url.endsWith('/participants')) return response(config, { data: comparisonPeople })
    if (config.params.participant_id.includes('b')) return new Promise(resolve => { finishOld = () => resolve(response(config, { data: comparisonResult(['a', 'b'], '旧结果') })) })
    return response(config, { data: comparisonResult(['a', 'c'], '新结果') })
  }
  const { controller } = await createComparison(t)
  controller.selected.value = ['a', 'b']
  await flushRequests()
  assert.equal(controller.state.value, 'loading')
  controller.selected.value = ['a', 'c']
  await flushRequests()
  assert.equal(controller.result.value.races[0].name, '新结果')
  finishOld()
  await flushRequests()
  assert.equal(controller.result.value.races[0].name, '新结果')
})

test('head to head reloads with applied filters and distinguishes empty results from errors', async t => {
  let fail = true
  respond = config => {
    if (config.url.endsWith('/participants')) return response(config, { data: comparisonPeople })
    if (fail) rejectRequest(config, 500, '加载失败')
    return response(config, { data: { participants: comparisonPeople.slice(0, 2), races: [] } })
  }
  const { controller, filters } = await createComparison(t)
  controller.selected.value = ['a', 'b']
  await flushRequests()
  assert.equal(controller.state.value, 'error')
  fail = false
  filters.value = { country: ['日本', '英国'], date_from: '2026-01-01' }
  await flushRequests()
  assert.equal(controller.state.value, 'empty')
  const last = requests.at(-1)
  assert.deepEqual(last.params.country, ['日本', '英国'])
  assert.equal(last.params.date_from, '2026-01-01')
})

test('expired access token is refreshed from the API envelope and the request succeeds', async () => {
  localStorage.setItem('auth', JSON.stringify({ accessToken: 'expired', refreshToken: 'refresh', user: { id: 1 } }))
  respond = config => {
    if (config.url === '/api/v1/auth/refresh') {
      assert.equal(JSON.parse(config.data).refresh_token, 'refresh')
      return response(config, { data: { access_token: 'renewed' } })
    }
    if (config.headers.Authorization === 'Bearer expired') rejectRequest(config, 401, 'expired')
    // Reject instead of returning 401 so a regression fails without waiting for navigation.
    assert.equal(config.headers.Authorization, 'Bearer renewed')
    return response(config, { data: 'loaded' })
  }
  const result = await apiClient.get('/races/1')
  assert.equal(result.data.data, 'loaded')
  assert.equal(JSON.parse(localStorage.getItem('auth')).accessToken, 'renewed')
  assert.equal(requests.length, 3)
  assert.equal(window.location.href, '')
})

for (const scenario of ['rejected refresh', 'rejected retry']) {
  test(`${scenario} clears the session and redirects without a refresh loop`, { timeout: 2000 }, async () => {
    localStorage.setItem('auth', JSON.stringify({ accessToken: 'expired', refreshToken: 'refresh' }))
    const navigation = new Promise(resolve => {
      Object.defineProperty(window.location, 'href', { set: resolve })
    })
    respond = config => {
      if (config.url === '/api/v1/auth/refresh') {
        if (scenario === 'rejected refresh') rejectRequest(config, 401, 'expired refresh', 'INVALID_REFRESH_TOKEN')
        return response(config, { data: { access_token: 'renewed' } })
      }
      rejectRequest(config, 401, 'expired')
    }
    // The interceptor deliberately leaves requests pending while navigating.
    void apiClient.get('/races/1')
    assert.equal(await navigation, '/login?session=expired&redirect=%2Fraces%2F1')
    assert.equal(localStorage.getItem('auth'), null)
    assert.equal(requests.filter(r => r.url === '/api/v1/auth/refresh').length, 1)
    assert.equal(requests.length, scenario === 'rejected retry' ? 3 : 2)
  })
}

for (const [label, previous, target] of [
  ['first vote', null, 2],
  ['change vote', 1, 2],
  ['cancel vote', 1, 1],
]) {
  test(`${label} failure restores both the horse name and selection, allowing a correct retry`, async () => {
    const vote = await createVote()
    vote.votedHorseName.value = previous === null ? null : `马${previous}`
    vote.votedRaceHorseId.value = previous
    let fail = true
    respond = config => {
      if (config.method === 'get') return response(config, { data: [] })
      if (fail) rejectRequest(config, 400, '投票已截止')
      return response(config, { data: { horse_name: `马${target}`, race_horse_id: target } })
    }
    await vote.toggleVote(horse(target), 1)
    assert.equal(vote.votedHorseName.value, previous === null ? null : `马${previous}`)
    assert.equal(vote.votedRaceHorseId.value, previous)
    assert.equal(vote.errorMessage.value, '投票已截止')
    assert.equal(vote.isSubmitting.value, false)

    fail = false
    await vote.toggleVote(horse(target), 1)
    const expectedMethod = target === previous ? 'delete' : 'post'
    assert.deepEqual(requests.filter(r => r.method !== 'get').map(r => r.method), [expectedMethod, expectedMethod])
    assert.equal(vote.votedRaceHorseId.value, expectedMethod === 'delete' ? null : target)
    assert.equal(vote.votedHorseName.value, expectedMethod === 'delete' ? null : `马${target}`)
    assert.equal(vote.errorMessage.value, null)
  })
}

function makeJwt(expSeconds) {
  const encode = obj => Buffer.from(JSON.stringify(obj)).toString('base64url')
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ sub: 'admin', exp: expSeconds })}.sig`
}

test('proactively refreshes an expired JWT access token before sending requests and deduplicates parallel calls', async () => {
  const nowSec = Math.floor(Date.now() / 1000)
  const expiredAccess = makeJwt(nowSec - 60)
  const validRefresh = makeJwt(nowSec + 7 * 86400)
  const renewedAccess = makeJwt(nowSec + 1800)

  localStorage.setItem('auth', JSON.stringify({
    accessToken: expiredAccess,
    refreshToken: validRefresh,
    user: { id: 1, username: 'admin', is_admin: true },
  }))

  respond = config => {
    if (config.url === '/api/v1/auth/refresh') {
      assert.equal(JSON.parse(config.data).refresh_token, validRefresh)
      return new Promise(resolve => setImmediate(() => resolve(response(config, { data: { access_token: renewedAccess } }))))
    }
    // Even if the endpoint never returns 401 (like a public endpoint), it must receive the renewed token directly.
    assert.equal(config.headers.Authorization, `Bearer ${renewedAccess}`)
    return response(config, { data: config.url })
  }

  const [racesRes, horsesRes] = await Promise.all([
    apiClient.get('/races'),
    apiClient.get('/horses'),
  ])

  assert.equal(racesRes.data.data, '/races')
  assert.equal(horsesRes.data.data, '/horses')
  assert.equal(JSON.parse(localStorage.getItem('auth')).accessToken, renewedAccess)
  assert.equal(requests.filter(r => r.url === '/api/v1/auth/refresh').length, 1)
  assert.equal(requests.length, 3)
  assert.equal(window.location.href, '')
})

test('expired JWT refresh token clears session and redirects before issuing requests', { timeout: 2000 }, async () => {
  const nowSec = Math.floor(Date.now() / 1000)
  localStorage.setItem('auth', JSON.stringify({
    accessToken: makeJwt(nowSec - 120),
    refreshToken: makeJwt(nowSec - 10),
    user: { id: 1, username: 'admin', is_admin: true },
  }))
  const navigation = new Promise(resolve => {
    Object.defineProperty(window.location, 'href', { set: resolve })
  })
  respond = config => response(config, { data: 'unexpected' })

  void apiClient.get('/races')
  assert.equal(await navigation, '/login?session=expired&redirect=%2Fraces%2F1')
  assert.equal(localStorage.getItem('auth'), null)
  assert.equal(requests.length, 0)
})

test('transient network failure during refresh preserves stored session instead of logging out', async () => {
  const nowSec = Math.floor(Date.now() / 1000)
  const validRefresh = makeJwt(nowSec + 7 * 86400)
  localStorage.setItem('auth', JSON.stringify({
    accessToken: makeJwt(nowSec - 60),
    refreshToken: validRefresh,
    user: { id: 1, username: 'admin', is_admin: true },
  }))

  respond = config => {
    if (config.url === '/api/v1/auth/refresh') {
      throw new axios.AxiosError('Network Error', 'ERR_NETWORK', config)
    }
    return response(config, { data: 'unexpected' })
  }

  await assert.rejects(() => apiClient.get('/races'), { message: 'Network Error' })
  assert.equal(JSON.parse(localStorage.getItem('auth')).refreshToken, validRefresh)
  assert.equal(window.location.href, '')
})

for (const proactive of [true, false]) {
  test(`${proactive ? 'proactive' : 'reactive'} refresh keeps the session after HTTP 503`, async () => {
    const now = Math.floor(Date.now() / 1000)
    const stored = JSON.stringify({
      accessToken: makeJwt(now + (proactive ? -60 : 60)),
      refreshToken: makeJwt(now + 3600),
    })
    localStorage.setItem('auth', stored)
    respond = config => {
      if (config.url === '/api/v1/auth/refresh') rejectRequest(config, 503, 'unavailable')
      rejectRequest(config, 401, 'expired')
    }

    await assert.rejects(apiClient.get('/races'), { message: 'unavailable' })
    assert.equal(localStorage.getItem('auth'), stored)
    assert.equal(window.location.href, '')
    assert.equal(requests.length, proactive ? 1 : 2)
  })
}

test('a malformed refresh response rejects without discarding the session', async () => {
  const stored = JSON.stringify({ accessToken: 'expired', refreshToken: 'refresh' })
  localStorage.setItem('auth', stored)
  respond = config => {
    if (config.url === '/api/v1/auth/refresh') {
      return response(config, { data: { access_token: ' ' } })
    }
    rejectRequest(config, 401, 'expired')
  }

  await assert.rejects(apiClient.get('/races'), { message: '刷新令牌响应缺少 access_token' })
  assert.equal(localStorage.getItem('auth'), stored)
  assert.equal(window.location.href, '')
})

for (const switchAccount of [false, true]) {
  test(`a pending refresh is canceled after ${switchAccount ? 'switching accounts' : 'logout'}`, async () => {
    const now = Math.floor(Date.now() / 1000)
    const refreshA = makeJwt(now + 3600)
    const refreshB = makeJwt(now + 7200)
    const accessB = makeJwt(now + 600)
    localStorage.setItem('auth', JSON.stringify({
      accessToken: makeJwt(now - 60), refreshToken: refreshA, user: { id: 1 },
    }))

    let finishOldRefresh
    const oldRefreshStarted = new Promise(resolve => {
      respond = config => {
        if (config.url === '/api/v1/auth/refresh') {
          if (JSON.parse(config.data).refresh_token === refreshA) {
            return new Promise(finish => {
              finishOldRefresh = () => finish(response(config, { data: { access_token: 'old' } }))
              resolve()
            })
          }
          assert.equal(JSON.parse(config.data).refresh_token, refreshB)
          return response(config, { data: { access_token: accessB } })
        }
        assert.equal(config.url, '/new-account')
        assert.equal(config.headers.Authorization, `Bearer ${accessB}`)
        return response(config, {})
      }
    })

    const canceled = assert.rejects(apiClient.post('/old-account'), axios.isCancel)
    await oldRefreshStarted
    localStorage.removeItem('auth')
    if (switchAccount) {
      localStorage.setItem('auth', JSON.stringify({
        accessToken: makeJwt(now - 30), refreshToken: refreshB, user: { id: 2 },
      }))
      await apiClient.get('/new-account')
    }
    const currentAuth = localStorage.getItem('auth')
    finishOldRefresh()
    await canceled

    assert.equal(localStorage.getItem('auth'), currentAuth)
    assert.equal(window.location.href, '')
    assert.equal(requests.some(config => config.url === '/old-account'), false)
  })
}

for (const failDuringRefresh of [false, true]) {
  test(`a late 401 from ${failDuringRefresh ? 'refresh' : 'the original request'} cannot affect a new session`, async () => {
    const now = Math.floor(Date.now() / 1000)
    const oldAuth = {
      sessionId: 'old',
      accessToken: makeJwt(now + (failDuringRefresh ? -60 : 60)),
      refreshToken: makeJwt(now + 3600),
    }
    localStorage.setItem('auth', JSON.stringify(oldAuth))
    let rejectOldRequest
    const oldRequestStarted = new Promise(resolve => {
      respond = config => {
        assert.equal(config.url, failDuringRefresh ? '/api/v1/auth/refresh' : '/old-account')
        return new Promise((_, reject) => {
          rejectOldRequest = () => reject(new axios.AxiosError('expired', 'ERR_BAD_REQUEST', config, null, {
            config, status: 401, statusText: 'Unauthorized', headers: {},
            data: { detail: { code: 'INVALID_REFRESH_TOKEN' } },
          }))
          resolve()
        })
      }
    })

    const canceled = assert.rejects(apiClient.post('/old-account'), axios.isCancel)
    await oldRequestStarted
    const newAuth = JSON.stringify({ ...oldAuth, sessionId: 'new' })
    localStorage.setItem('auth', newAuth)
    rejectOldRequest()
    await canceled

    assert.equal(localStorage.getItem('auth'), newAuth)
    assert.equal(window.location.href, '')
    assert.equal(requests.length, 1)
  })
}
