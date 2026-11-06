import assert from 'node:assert/strict'
import { after, before, beforeEach, test } from 'node:test'
import axios from 'axios'
import { createServer } from 'vite'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'

let server
let apiClient
let useVote
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

function rejectRequest(config, status, message) {
  throw new axios.AxiosError(message, 'ERR_BAD_REQUEST', config, null, {
    config, status, statusText: 'Error', headers: {},
    data: { detail: { message } },
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

for (const scenario of ['missing token', 'empty token', 'rejected refresh', 'rejected retry']) {
  test(`${scenario} clears the session and redirects without a refresh loop`, { timeout: 2000 }, async () => {
    localStorage.setItem('auth', JSON.stringify({ accessToken: 'expired', refreshToken: 'refresh' }))
    const navigation = new Promise(resolve => {
      Object.defineProperty(window.location, 'href', { set: resolve })
    })
    respond = config => {
      if (config.url === '/api/v1/auth/refresh') {
        if (scenario === 'rejected refresh') rejectRequest(config, 401, 'expired refresh')
        const data = scenario === 'missing token' ? {} : {
          access_token: scenario === 'empty token' ? '   ' : 'renewed',
        }
        return response(config, { data })
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
