const TOKEN_KEY = 'llmchat_token'
const NAME_KEY = 'llmchat_username'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function getUsername() {
  return localStorage.getItem(NAME_KEY) || ''
}
export function setAuth(token, username) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(NAME_KEY, username)
}
export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(NAME_KEY)
}

function authHeaders() {
  const t = getToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

async function raiseForStatus(res) {
  if (res.ok) return
  if (res.status === 401) {
    clearAuth()
    location.hash = '#/login'
  }
  let detail = `HTTP ${res.status}`
  try {
    const body = await res.json()
    if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch { /* не JSON — оставляем код */ }
  throw new Error(detail)
}

export async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch('/api' + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  await raiseForStatus(res)
  return res.json()
}

/**
 * Отправка сообщения со стримингом ответа (SSE поверх fetch,
 * потому что EventSource не умеет POST и заголовки).
 */
export async function streamChat(dialogId, content, { onStart, onDelta, onDone, onError }) {
  const res = await fetch(`/api/dialogs/${dialogId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ content }),
  })
  await raiseForStatus(res)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      let event = 'message'
      const dataLines = []
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
      }
      const data = dataLines.join('\n')
      if (event === 'start') onStart?.(JSON.parse(data))
      else if (event === 'delta') onDelta?.(data)
      else if (event === 'done') onDone?.(JSON.parse(data))
      else if (event === 'error') onError?.(data)
    }
  }
}
