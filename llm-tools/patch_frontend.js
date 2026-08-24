/**
 * ЗАПЛАТКА для фронта. НЕОБЯЗАТЕЛЬНАЯ.
 *
 * Без неё всё работает: разбор событий в api.js сделан цепочкой if/else if,
 * поэтому незнакомые типы (tool_call, tool_result, confirm) просто
 * игнорируются, ничего не ломается.
 *
 * Нужна она для другого. С инструментами ответ приходит не дельтами по токену,
 * а куском — пока модель решает, какую ручку дёрнуть, показывать нечего.
 * Цепочка из трёх шагов на замерах заняла около тридцати секунд, и всё это
 * время экран молчит и выглядит зависшим. Строка «обращаюсь к …» снимает этот
 * вопрос целиком.
 */

// ===========================================================================
// ШАГ 1. frontend/src/api.js — принять новые события
//
// В streamChat расширить список параметров и добавить три ветки в разбор.
// ===========================================================================

export async function streamChat(dialogId, content, {
  think, onStart, onStatus, onThink, onDelta, onDone, onError,
  onToolCall, onToolResult, onConfirm,   // <-- ДОБАВИТЬ
}) {
  // ... без изменений до разбора событий ...

  // в цепочке разбора, рядом с существующими ветками:
  if (event === 'start') onStart?.(JSON.parse(data))
  else if (event === 'status') onStatus?.(data)
  else if (event === 'think') onThink?.(data)
  else if (event === 'delta') onDelta?.(data)
  else if (event === 'tool_call') onToolCall?.(JSON.parse(data))       // ДОБАВИТЬ
  else if (event === 'tool_result') onToolResult?.(JSON.parse(data))   // ДОБАВИТЬ
  else if (event === 'confirm') onConfirm?.(JSON.parse(data))          // ДОБАВИТЬ
  else if (event === 'done') onDone?.(JSON.parse(data))
  else if (event === 'error') onError?.(data)
}


// ===========================================================================
// ШАГ 2. frontend/src/views/ChatView.vue — показать обращения
//
// Рядом с состоянием, где уже живёт статус «сжимаю историю»:
//     const toolSteps = ref([])
//
// В вызов streamChat добавить обработчики:
// ===========================================================================

onToolCall: (ev) => {
  toolSteps.value.push({ name: ev.name, args: ev.args, state: 'running' })
},

onToolResult: (ev) => {
  const step = [...toolSteps.value].reverse().find(s => s.name === ev.name && s.state === 'running')
  if (step) {
    step.state = ev.ok ? 'ok' : 'failed'
    step.preview = ev.preview
  }
},

// ЗАГЛУШКА. Подтверждение изменяющих вызовов.
//
// Прилетает, когда модель просит ручку с is_mutating = 1. В tools_loop.py
// такой вызов сейчас записывается в журнал со статусом pending и отклоняется,
// поэтому здесь пока достаточно показать пользователю, что произошло.
//
// Чтобы довести до конца, нужны: кнопка «Выполнить» с показом ручки и
// аргументов, ручка POST /api/tool_calls/{call_id}/confirm на бэкенде и
// продолжение диалога с этого места. Разрыв потока обязателен — внутри
// одного SSE-соединения дождаться нажатия нельзя.
onConfirm: (ev) => {
  toolSteps.value.push({
    name: ev.name, args: ev.args, state: 'needs_confirm', callId: ev.call_id,
  })
},

// Сбрасывать toolSteps в начале каждого нового сообщения, в onStart —
// иначе обращения копятся через все сообщения диалога.


// ===========================================================================
// ШАГ 3. Разметка. Над ответом, рядом с блоком размышлений.
// ===========================================================================
/*
<div v-if="toolSteps.length" class="tools">
  <div v-for="(s, i) in toolSteps" :key="i" class="tool-step" :class="s.state">
    <span v-if="s.state === 'running'">обращаюсь к {{ s.name }}…</span>
    <span v-else-if="s.state === 'ok'">{{ s.name }} — получено</span>
    <span v-else-if="s.state === 'needs_confirm'">{{ s.name }} — нужно подтверждение</span>
    <span v-else>{{ s.name }} — не удалось</span>
  </div>
</div>
*/

// Аргументы вызова показывать стоит: это единственное место, где видно, что
// именно модель собралась спросить у внутренней системы. Прятать их — значит
// лишить пользователя возможности заметить, что вопрос понят неверно.
