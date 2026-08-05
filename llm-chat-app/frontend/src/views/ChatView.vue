<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, clearAuth, getUsername, streamChat } from '../api'

const router = useRouter()
const username = getUsername()

const dialogs = ref([])
const models = ref([])
const llmWarning = ref('')
const activeId = ref(null)
const messages = ref([])
const draft = ref('')
const busy = ref(false)
const error = ref('')
const messagesEl = ref(null)
// счётчик временных ключей: пока сообщение не сохранено, id ему нужен всё равно,
// а одинаковые ключи в v-for заставляют Vue переиспользовать чужие узлы
let tmpSeq = 0

const activeDialog = () => dialogs.value.find((d) => d.id === activeId.value) || null

async function loadModels() {
  const res = await api('/models')
  models.value = res.models || []
  llmWarning.value = res.error ? 'LLM-сервер недоступен: запустите scripts\\run_llm.bat' : ''
}

async function loadDialogs() {
  dialogs.value = await api('/dialogs')
  if (!activeId.value && dialogs.value.length) await selectDialog(dialogs.value[0].id)
}

async function selectDialog(id) {
  activeId.value = id
  error.value = ''
  messages.value = await api(`/dialogs/${id}/messages`)
  scrollDown()
}

async function newDialog() {
  const d = await api('/dialogs', { method: 'POST', body: { model_name: models.value[0]?.name || null } })
  dialogs.value.unshift(d)
  await selectDialog(d.id)
}

async function removeDialog(id) {
  if (!confirm('Удалить диалог вместе с сообщениями?')) return
  await api(`/dialogs/${id}`, { method: 'DELETE' })
  dialogs.value = dialogs.value.filter((d) => d.id !== id)
  if (activeId.value === id) {
    activeId.value = null
    messages.value = []
    if (dialogs.value.length) await selectDialog(dialogs.value[0].id)
  }
}

async function changeModel(e) {
  const d = activeDialog()
  if (!d) return
  const updated = await api(`/dialogs/${d.id}`, { method: 'PATCH', body: { model_name: e.target.value } })
  d.model_name = updated.model_name
}

function scrollDown() {
  nextTick(() => {
    const el = messagesEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function send() {
  const text = draft.value.trim()
  if (!text || busy.value) return
  if (!activeId.value) await newDialog()
  const d = activeDialog()
  busy.value = true
  error.value = ''
  draft.value = ''

  tmpSeq += 1
  const userMsg = { id: `tmp-u-${tmpSeq}`, role: 'user', content: text }
  const assistant = { id: `tmp-a-${tmpSeq}`, role: 'assistant', content: '' }
  messages.value.push(userMsg, assistant)
  scrollDown()

  try {
    await streamChat(d.id, text, {
      onStart: (meta) => {
        if (meta.dialog_title) d.title = meta.dialog_title
        // подменяем временные ключи настоящими id из базы
        if (meta.user_message_id) userMsg.id = meta.user_message_id
      },
      onDelta: (delta) => {
        assistant.content += delta
        scrollDown()
      },
      onDone: (meta) => {
        if (meta.assistant_message_id) assistant.id = meta.assistant_message_id
      },
      onError: (msg) => {
        error.value = msg
      },
    })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
    scrollDown()
  }
}

function onComposerKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

async function logout() {
  try { await api('/auth/logout', { method: 'POST' }) } catch { /* токен мог истечь */ }
  clearAuth()
  router.push('/login')
}

onMounted(async () => {
  try {
    await Promise.all([loadModels(), loadDialogs()])
  } catch (e) {
    error.value = e.message
  }
})
</script>

<template>
  <div class="chat-layout">
    <aside class="sidebar">
      <div class="sidebar-head">
        <button class="primary wide" @click="newDialog">+ Новый диалог</button>
      </div>
      <nav class="dialog-list">
        <div
          v-for="d in dialogs"
          :key="d.id"
          class="dialog-item"
          :class="{ active: d.id === activeId }"
          @click="selectDialog(d.id)"
        >
          <span class="dialog-title">{{ d.title }}</span>
          <button class="ghost del" title="Удалить" @click.stop="removeDialog(d.id)">×</button>
        </div>
        <p v-if="!dialogs.length" class="hint">Диалогов пока нет</p>
      </nav>
      <div class="sidebar-foot">
        <span class="user">{{ username }}</span>
        <button class="ghost" @click="logout">Выйти</button>
      </div>
    </aside>

    <main class="chat-main">
      <header class="chat-head">
        <span class="chat-title">{{ activeDialog()?.title || 'LLM Chat' }}</span>
        <label class="model-pick" v-if="activeDialog()">
          Модель
          <select :value="activeDialog()?.model_name || ''" @change="changeModel">
            <option value="" disabled>— выберите —</option>
            <option v-for="m in models" :key="m.name" :value="m.name">
              {{ m.name }} ({{ m.size_mb }} МБ){{ m.loaded ? ' — загружена' : '' }}
            </option>
          </select>
        </label>
      </header>

      <p v-if="llmWarning" class="banner warn">{{ llmWarning }}</p>
      <p v-if="error" class="banner error">{{ error }}</p>

      <section class="messages" ref="messagesEl">
        <p v-if="!messages.length && activeId" class="hint center">Напишите первое сообщение</p>
        <p v-if="!activeId" class="hint center">Создайте диалог слева</p>
        <div v-for="m in messages" :key="m.id" class="msg" :class="m.role">
          <div class="bubble">
            <span v-if="m.role === 'assistant' && !m.content && busy" class="typing">думает…</span>
            <template v-else>{{ m.content }}</template>
          </div>
        </div>
      </section>

      <footer class="composer">
        <textarea
          v-model="draft"
          rows="2"
          placeholder="Сообщение… (Enter — отправить, Shift+Enter — перенос)"
          :disabled="busy || !activeId && !models.length"
          @keydown="onComposerKeydown"
        ></textarea>
        <button class="primary" :disabled="busy || !draft.trim()" @click="send">
          {{ busy ? '…' : 'Отправить' }}
        </button>
      </footer>
    </main>
  </div>
</template>
