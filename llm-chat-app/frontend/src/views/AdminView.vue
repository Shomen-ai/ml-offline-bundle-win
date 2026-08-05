<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const values = ref({})
const saved = ref({})       // снимок сохранённого — по нему считаем изменённые поля
const spec = ref([])
const models = ref([])
const busy = ref(false)
const error = ref('')
const notice = ref('')

const coldKeys = computed(() => spec.value.filter((s) => s.cold).map((s) => s.key))

// thinking_models хранится строкой через запятую, а правится галочками
// по реальному списку моделей — руками имена файлов набирать незачем
const thinkingList = computed(() =>
  String(values.value.thinking_models || '').split(',').map((s) => s.trim()).filter(Boolean),
)
// имена, которых больше нет в папке моделей: файл переименовали или убрали.
// Показываем отдельно, чтобы настройка не пропадала молча
const thinkingMissing = computed(() =>
  thinkingList.value.filter((n) => !models.value.some((m) => m.name === n)),
)

function toggleThinking(name, on) {
  const next = on
    ? [...thinkingList.value, name]
    : thinkingList.value.filter((n) => n !== name)
  values.value.thinking_models = next.join(', ')
}
const titles = computed(() => Object.fromEntries(spec.value.map((s) => [s.key, s.title])))

const dirtyKeys = computed(() =>
  Object.keys(values.value).filter((k) => String(values.value[k]) !== String(saved.value[k])),
)
const coldDirty = computed(() => dirtyKeys.value.filter((k) => coldKeys.value.includes(k)))

async function load() {
  const res = await api('/admin/settings')
  values.value = { ...res.values }
  saved.value = { ...res.values }
  spec.value = res.spec
  try {
    const m = await api('/admin/models')
    models.value = m.models || []
    if (m.error) error.value = `LLM-сервер недоступен: ${m.error}`
  } catch (e) {
    error.value = e.message
  }
}

async function save() {
  error.value = ''
  notice.value = ''
  if (!dirtyKeys.value.length) {
    notice.value = 'Менять нечего — настройки уже сохранены'
    return
  }
  if (coldDirty.value.length) {
    const names = coldDirty.value.map((k) => titles.value[k] || k).join(', ')
    const ok = confirm(
      `Изменение таких настроек перезагружает модель: ${names}.\n\n` +
        'Веса будут выгружены из видеопамяти и загружены заново. ' +
        'Ответы, которые генерируются прямо сейчас, оборвутся, а первый запрос ' +
        'после перезагрузки будет ждать загрузку модели.\n\nПродолжить?',
    )
    if (!ok) return
  }

  busy.value = true
  try {
    const patch = Object.fromEntries(dirtyKeys.value.map((k) => [k, values.value[k]]))
    const res = await api('/admin/settings', { method: 'PUT', body: patch })
    values.value = { ...res.values }
    saved.value = { ...res.values }
    if (res.reload_error) error.value = `Настройки сохранены, но модель не перезагрузилась: ${res.reload_error}`
    else if (res.reloaded) notice.value = 'Сохранено, модель перезагружена'
    else notice.value = 'Сохранено'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  try {
    await load()
  } catch (e) {
    error.value = e.message
  }
})
</script>

<template>
  <div class="admin-page">
    <header class="admin-head">
      <h1>Настройки LLM</h1>
      <router-link class="ghost" to="/chat">← К чату</router-link>
    </header>

    <p v-if="error" class="banner error">{{ error }}</p>
    <p v-if="notice" class="banner">{{ notice }}</p>

    <form class="admin-form" @submit.prevent="save">
      <label>
        Модель
        <select v-model="values.model_name">
          <option value="">— первая доступная —</option>
          <option v-for="m in models" :key="m.name" :value="m.name">
            {{ m.name }} ({{ m.size_mb }} МБ){{ m.loaded ? ' — загружена' : '' }}
          </option>
        </select>
        <small class="hint">Перезагружает модель</small>
      </label>

      <label>
        Размер контекста, токенов
        <input v-model.number="values.n_ctx" type="number" min="512" max="131072" />
        <small class="hint">Перезагружает модель. Больше контекст — больше видеопамяти</small>
      </label>

      <label>
        Слоёв на GPU
        <input v-model.number="values.n_gpu_layers" type="number" min="-1" max="999" />
        <small class="hint">Перезагружает модель. −1 — все слои на видеокарте</small>
      </label>

      <label>
        Температура
        <input v-model.number="values.temperature" type="number" min="0" max="2" step="0.1" />
        <small class="hint">0 — предсказуемо, выше — разнообразнее</small>
      </label>

      <label>
        Потолок длины ответа, токенов
        <input v-model.number="values.max_tokens" type="number" min="1" max="8192" />
      </label>

      <label>
        Размышления по умолчанию
        <select v-model="values.thinking_enabled">
          <option :value="true">включены</option>
          <option :value="false">выключены</option>
        </select>
        <small class="hint">Пользователь может переключить в чате</small>
      </label>

      <div class="wide field">
        <span class="field-title">Модели с поддержкой размышлений</span>
        <div class="checks">
          <label v-for="m in models" :key="m.name" class="check">
            <input
              type="checkbox"
              :checked="thinkingList.includes(m.name)"
              @change="toggleThinking(m.name, $event.target.checked)"
            />
            {{ m.name }}
          </label>
          <label v-for="name in thinkingMissing" :key="name" class="check missing">
            <input type="checkbox" checked @change="toggleThinking(name, false)" />
            {{ name }} — файла нет в папке моделей
          </label>
          <p v-if="!models.length && !thinkingMissing.length" class="hint">
            Список моделей недоступен — не поднят LLM-сервер
          </p>
        </div>
        <small class="hint">У остальных моделей тумблер размышлений в чате не показывается</small>
      </div>

      <label class="wide">
        Системный промпт
        <textarea v-model="values.system_prompt" rows="8"
          placeholder="Например: Отвечай по-русски, кратко и по делу."></textarea>
        <small class="hint">Уходит первым сообщением в каждом диалоге. Пусто — не подставляется</small>
      </label>

      <div class="admin-actions">
        <button class="primary" type="submit" :disabled="busy">
          {{ busy ? 'Сохраняю…' : 'Сохранить настройки' }}
        </button>
        <span v-if="coldDirty.length" class="hint warn-text">
          Будет перезагружена модель: {{ coldDirty.map((k) => titles[k] || k).join(', ') }}
        </span>
        <span v-else-if="dirtyKeys.length" class="hint">Изменений: {{ dirtyKeys.length }}</span>
      </div>
    </form>
  </div>
</template>

<style scoped>
.admin-page { max-width: 760px; margin: 0 auto; padding: 24px 16px 48px; }
.admin-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.admin-head h1 { font-size: 20px; margin: 0 0 16px; }
.admin-form { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.admin-form label { display: flex; flex-direction: column; gap: 6px; }
.admin-form label.wide, .admin-form .wide { grid-column: 1 / -1; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-title { font-weight: 600; }
.checks { display: flex; flex-direction: column; gap: 4px; }
.check { flex-direction: row !important; align-items: center; gap: 8px; font-weight: normal; }
.check.missing { color: #b26a00; }
.admin-form small { font-weight: normal; }
.admin-actions { grid-column: 1 / -1; display: flex; align-items: center; gap: 12px; }
.warn-text { color: #b26a00; }
@media (max-width: 640px) { .admin-form { grid-template-columns: 1fr; } }
</style>
