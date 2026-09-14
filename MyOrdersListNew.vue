<template>
  <div class="w-full space-y-3">
    <!-- ПАНЕЛЬ: поиск, экспорт, сброс -->
    <div class="bg-white rounded-xl border border-slate-200 p-3">
      <div class="flex flex-wrap items-center gap-2">
        <div class="relative flex-1 min-w-[220px]">
          <i class="pi pi-search absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm" />
          <InputText
            v-model="filters.global.value"
            placeholder="Номер, ФИО, подразделение, гараж…"
            class="w-full h-10 pl-10 rounded-lg"
            @input="trimFilterValue(filters.global)"
          />
          <button
            v-if="filters.global.value"
            class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600"
            @click="filters.global.value = null"
          >
            <i class="pi pi-times text-xs" />
          </button>
        </div>

        <Button
          icon="pi pi-file-excel"
          label="Excel"
          class="h-10 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-lg"
          @click="exportToExcel"
        />
        <Button
          v-if="hasActiveFilters"
          icon="pi pi-filter-slash"
          label="Сбросить"
          class="h-10 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-lg"
          @click="clearFilter"
        />
      </div>
    </div>

    <!-- ПЛИТКИ СТАТУСОВ -->
    <div class="grid gap-2 grid-cols-[repeat(auto-fit,minmax(150px,1fr))]">
      <button
        v-for="tile in statusTiles"
        :key="tile.id ?? 'all'"
        type="button"
        class="flex items-center gap-3 px-4 h-14 rounded-xl border text-left transition-colors outline-none
               focus-visible:ring-2 focus-visible:ring-blue-500/40"
        :class="activeStatus === tile.id
          ? 'bg-blue-50 border-blue-300'
          : 'bg-white border-slate-200 mouse:hover:border-slate-300'"
        @click="setStatus(tile.id)"
      >
        <span
          class="shrink-0 size-8 rounded-lg grid place-items-center"
          :class="tile.iconBg"
        >
          <i :class="['pi', tile.icon, 'text-sm', tile.iconColor]" />
        </span>
        <span class="min-w-0">
          <span class="block text-xs text-slate-500 truncate">{{ tile.label }}</span>
          <span class="block text-lg font-semibold leading-tight tabular-nums text-slate-900">
            {{ tile.count }}
          </span>
        </span>
      </button>
    </div>

    <!-- СПИСОК -->
    <div v-if="displayedCustomers.length" class="space-y-2">
      <article
        v-for="order in displayedCustomers"
        :key="order.id"
        class="bg-white rounded-xl border overflow-hidden transition-colors"
        :class="isOpen(order.id) ? 'border-blue-300' : 'border-slate-200'"
      >
        <!-- ШАПКА КАРТОЧКИ -->
        <button
          type="button"
          class="w-full text-left px-4 py-3 flex items-center gap-4 outline-none
                 focus-visible:bg-slate-50 mouse:hover:bg-slate-50 transition-colors
                 pointer-coarse:py-4"
          :aria-expanded="isOpen(order.id)"
          @click="toggle(order.id)"
        >
          <!-- номер + заказчик -->
          <div class="w-40 shrink-0 min-w-0">
            <div class="font-semibold tabular-nums text-slate-900">{{ order.id }}</div>
            <div class="text-xs text-slate-500 truncate">
              {{ shortFio(order.fio) }}<template v-if="order.podr"> · {{ order.podr }}</template>
            </div>
          </div>

          <!-- статус -->
          <span
            class="shrink-0 px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap"
            :class="statusClass(order.state?.id)"
          >
            {{ getStatusLabel(order.state) }}
          </span>

          <!-- маршрут -->
          <div class="flex-1 min-w-0 hidden sm:block">
            <div class="text-sm text-slate-700 truncate">{{ routeSummary(order) }}</div>
            <div class="text-xs text-slate-400">
              {{ getLoadingCount(order) }} погр. · {{ getUnloadingCount(order) }} выгр.
            </div>
          </div>

          <!-- когда нужна машина -->
          <div class="w-44 shrink-0 hidden lg:block min-w-0">
            <div class="text-sm text-slate-700 truncate">
              {{ getLoadingDates(order.loading_and_delivery_points) }}
            </div>
          </div>

          <!-- транспорт -->
          <div class="w-40 shrink-0 hidden md:block min-w-0">
            <div class="text-sm text-slate-700 truncate">
              {{ order.car?.transport_type?.type ?? '—' }}
            </div>
            <div class="text-xs text-slate-400 truncate">{{ order.car?.garaj_number ?? '—' }}</div>
          </div>

          <i
            class="pi pi-chevron-down shrink-0 text-slate-400 text-sm transition-transform duration-200"
            :class="{ 'rotate-180': isOpen(order.id) }"
          />
        </button>

        <!-- РАСКРЫТИЕ -->
        <div v-if="isOpen(order.id)" class="border-t border-slate-100 bg-slate-50/60 px-4 py-4">
          <!-- маршрут -->
          <div class="mb-5">
            <h3 class="text-xs font-medium text-slate-500 mb-2">Маршрут</h3>
            <ol v-if="points(order).length" class="space-y-2">
              <li
                v-for="(p, i) in points(order)"
                :key="i"
                class="flex items-start gap-3"
              >
                <span
                  class="shrink-0 size-6 rounded-full grid place-items-center text-[11px] font-semibold text-white"
                  :class="p.type === 'loading' ? 'bg-emerald-600' : 'bg-orange-500'"
                >{{ i + 1 }}</span>
                <div class="min-w-0 text-sm">
                  <div class="text-slate-900">
                    <span class="font-medium">{{ p.type === 'loading' ? 'Погрузка' : 'Выгрузка' }}</span>
                    <span class="text-slate-500"> · </span>{{ pointPlace(p) }}
                  </div>
                  <div v-if="pointDate(p)" class="text-xs text-slate-500 mt-0.5">{{ pointDate(p) }}</div>
                </div>
              </li>
            </ol>
            <p v-else class="text-sm text-slate-400">Точки не указаны</p>
          </div>

          <!-- груз + контакты -->
          <div class="grid gap-x-8 gap-y-5 grid-cols-[repeat(auto-fit,minmax(260px,1fr))]">
            <div class="min-w-0">
              <h3 class="text-xs font-medium text-slate-500 mb-2">Груз</h3>
              <dl v-if="cargo(order).length" class="text-sm space-y-1">
                <div v-for="(row, i) in cargo(order)" :key="i" class="flex gap-3">
                  <dt class="text-slate-500 w-40 shrink-0 truncate">{{ row.label }}</dt>
                  <dd class="text-slate-900 min-w-0 break-words">{{ row.value }}</dd>
                </div>
              </dl>
              <p v-else class="text-sm text-slate-400">Не заполнено</p>
            </div>

            <div class="min-w-0">
              <h3 class="text-xs font-medium text-slate-500 mb-2">Контакты и исполнение</h3>
              <dl class="text-sm space-y-1">
                <div class="flex gap-3">
                  <dt class="text-slate-500 w-40 shrink-0">Телефоны</dt>
                  <dd class="text-slate-900 tabular-nums">
                    {{ [order.stat_number, order.mob_number].filter(Boolean).join(' · ') || '—' }}
                  </dd>
                </div>
                <div class="flex gap-3">
                  <dt class="text-slate-500 w-40 shrink-0">Водитель</dt>
                  <dd class="text-slate-900">{{ order.driver?.fio ?? 'не назначен' }}</dd>
                </div>
                <div class="flex gap-3">
                  <dt class="text-slate-500 w-40 shrink-0">Заявка создана</dt>
                  <dd class="text-slate-900 tabular-nums">{{ safeFormatDate(order.created_at) }}</dd>
                </div>
                <div v-if="order.provide_car_time" class="flex gap-3">
                  <dt class="text-slate-500 w-40 shrink-0">Машина подана</dt>
                  <dd class="text-slate-900 tabular-nums">{{ safeFormatDate(order.provide_car_time) }}</dd>
                </div>
                <div v-if="order.complite_order_time" class="flex gap-3">
                  <dt class="text-slate-500 w-40 shrink-0">Заявка закрыта</dt>
                  <dd class="text-slate-900 tabular-nums">{{ safeFormatDate(order.complite_order_time) }}</dd>
                </div>
                <div v-if="order.dispatcher_comments" class="flex gap-3">
                  <dt class="text-slate-500 w-40 shrink-0">От диспетчера</dt>
                  <dd class="text-slate-900 break-words">{{ order.dispatcher_comments }}</dd>
                </div>
              </dl>
            </div>
          </div>

          <div class="mt-5 pt-4 border-t border-slate-200 flex flex-wrap gap-2">
            <Button
              icon="pi pi-eye"
              label="Открыть заявку"
              class="h-10 bg-blue-600 hover:bg-blue-700 text-white border-none rounded-lg"
              @click.stop="emit('openModal', order)"
            />
            <slot name="row-actions" :order="order" />
          </div>
        </div>
      </article>

      <div v-if="displayedCustomers.length < filteredCustomers.length" class="pt-1">
        <Button
          label="Показать ещё"
          icon="pi pi-angle-down"
          class="w-full h-11 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-xl"
          @click="loadMore"
        />
        <p class="text-center text-xs text-slate-400 mt-2 tabular-nums">
          {{ displayedCustomers.length }} из {{ filteredCustomers.length }}
        </p>
      </div>
    </div>

    <!-- ПУСТО -->
    <div v-else class="bg-white rounded-xl border border-slate-200 py-12 text-center">
      <i class="pi pi-inbox text-3xl text-slate-300" />
      <p class="mt-3 text-slate-600">Заявок нет</p>
      <p class="mt-1 text-sm text-slate-400">
        {{ hasActiveFilters ? 'Измените условия поиска или сбросьте фильтры' : 'Здесь появятся поданные заявки' }}
      </p>
      <Button
        v-if="hasActiveFilters"
        label="Сбросить фильтры"
        class="mt-4 h-10 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-lg"
        @click="clearFilter"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import * as XLSX from 'xlsx-js-style'
import { formatDate, formatDateDetailed } from '../Composables/formatDate'
import { useTrimFilter } from '@/components/Composables/useTrimFilter.js'

const props = defineProps(['columns', 'customers'])
const emit = defineEmits(['openModal'])

const { trimFilterValue } = useTrimFilter()

const filters = ref({ global: { value: null } })
const activeStatus = ref(null)
const visibleLimit = ref(15)
const openIds = ref(new Set())

/* ---------- статусы ---------- */

const STATUS = {
  1: { label: 'Необработана', chip: 'bg-blue-100 text-blue-700' },
  2: { label: 'Доработка', chip: 'bg-amber-100 text-amber-700' },
  3: { label: 'Передана', chip: 'bg-violet-100 text-violet-700' },
  4: { label: 'В процессе', chip: 'bg-cyan-100 text-cyan-700' },
  5: { label: 'Завершена', chip: 'bg-emerald-100 text-emerald-700' },
}

const getStatusLabel = (state) => STATUS[state?.id]?.label ?? state?.state ?? 'Неизвестно'
const statusClass = (id) => STATUS[id]?.chip ?? 'bg-slate-100 text-slate-600'

const statusTiles = computed(() => {
  const all = props.customers ?? []
  const countBy = (id) => all.filter((o) => o.state?.id === id).length
  return [
    { id: null, label: 'Все заявки', count: all.length, icon: 'pi-list', iconBg: 'bg-slate-100', iconColor: 'text-slate-600' },
    { id: 1, label: 'Необработанные', count: countBy(1), icon: 'pi-clock', iconBg: 'bg-blue-100', iconColor: 'text-blue-600' },
    { id: 2, label: 'На доработке', count: countBy(2), icon: 'pi-pencil', iconBg: 'bg-amber-100', iconColor: 'text-amber-600' },
    { id: 4, label: 'В процессе', count: countBy(4), icon: 'pi-truck', iconBg: 'bg-cyan-100', iconColor: 'text-cyan-600' },
    { id: 5, label: 'Завершённые', count: countBy(5), icon: 'pi-check-circle', iconBg: 'bg-emerald-100', iconColor: 'text-emerald-600' },
  ]
})

function setStatus(id) {
  activeStatus.value = activeStatus.value === id ? null : id
}

/* ---------- фильтрация ---------- */

const hasActiveFilters = computed(
  () => Boolean(filters.value.global.value) || activeStatus.value !== null
)

const filteredCustomers = computed(() => {
  let result = props.customers ?? []

  if (activeStatus.value !== null) {
    result = result.filter((o) => o.state?.id === activeStatus.value)
  }

  const q = filters.value.global.value?.trim().toLowerCase()
  if (q) {
    result = result.filter((o) =>
      [
        o.id,
        o.fio,
        o.podr,
        o.car?.garaj_number,
        o.car?.transport_type?.type,
        o.driver?.fio,
        o.stat_number,
        o.mob_number,
        o.comments,
        o.state?.state,
      ]
        .map((v) => String(v ?? '').toLowerCase())
        .some((v) => v.includes(q))
    )
  }

  return result
})

const displayedCustomers = computed(() => filteredCustomers.value.slice(0, visibleLimit.value))

const loadMore = () => { visibleLimit.value += 15 }

watch(filteredCustomers, () => { visibleLimit.value = 15 })

function clearFilter() {
  filters.value.global.value = null
  activeStatus.value = null
}

/* ---------- раскрытие ---------- */

const isOpen = (id) => openIds.value.has(id)

function toggle(id) {
  const next = new Set(openIds.value)
  next.has(id) ? next.delete(id) : next.add(id)
  openIds.value = next
}

/* ---------- данные заявки ---------- */

function shortFio(fio) {
  if (!fio) return '—'
  const [f, i, o] = String(fio).trim().split(/\s+/)
  return [f, i && `${i[0]}.`, o && `${o[0]}.`].filter(Boolean).join(' ')
}

const points = (order) =>
  Array.isArray(order.loading_and_delivery_points) ? order.loading_and_delivery_points : []

function pointPlace(p) {
  const parts = []
  if (p.building) parts.push(`Корпус ${p.building}`)
  if (p.x_cord) parts.push(`X-${p.x_cord}`)
  if (p.y_cord) parts.push(`Y-${p.y_cord}`)
  return parts.join(', ') || 'место не указано'
}

function pointDate(p) {
  if (!Array.isArray(p.date) || !p.date.length) return ''
  const a = formatDate(p.date[0])
  const b = p.date[1] ? formatDate(p.date[1]) : null
  return b && b !== a ? `${a} — ${b}` : a
}

function routeSummary(order) {
  const list = points(order)
  if (!list.length) return 'Маршрут не указан'
  const names = list.map((p) => (p.building ? `Корпус ${p.building}` : '?'))
  if (names.length <= 2) return names.join(' → ')
  return `${names[0]} → +${names.length - 2} → ${names.at(-1)}`
}

function getLoadingCount(order) {
  return points(order).filter((p) => p.type === 'loading').length
}

function getUnloadingCount(order) {
  return points(order).filter((p) => p.type === 'unloading').length
}

function getLoadingDates(list) {
  if (!Array.isArray(list)) return '—'
  const first = list.find((p) => p.type === 'loading')
  if (!first?.date?.length) return '—'
  const dates = first.date.map((d) => formatDateDetailed(d)).filter(Boolean)
  if (!dates.length) return '—'
  const broken = !dates[1] || dates[0] === dates[1] || dates.includes('01.01.1970 04:00')
  return broken ? `На ${dates[0]}` : `С ${dates[0]} по ${dates[1]}`
}

// comments приходит склеенной строкой "Ключ: значение\nКлюч: значение"
function cargo(order) {
  if (!order.comments) return []
  return String(order.comments)
    .split('\n')
    .map((line) => {
      const idx = line.indexOf(':')
      if (idx === -1) return { label: '', value: line.trim() }
      return { label: line.slice(0, idx).trim(), value: line.slice(idx + 1).trim() }
    })
    .filter((r) => r.value)
}

function safeFormatDate(value) {
  try {
    return value ? formatDate(value) : '—'
  } catch {
    return '—'
  }
}

/* ---------- экспорт ---------- */

function exportToExcel() {
  const cols = props.columns ?? []
  const headers = cols.map((c) => c.header)
  const fields = cols.map((c) => c.field)

  const rows = filteredCustomers.value.map((row) =>
    fields.map((field) => field.split('.').reduce((acc, k) => acc?.[k], row) ?? '')
  )

  const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows])

  worksheet['!cols'] = headers.map((h, i) => ({
    wch: Math.max(10, h.length, ...rows.map((r) => String(r[i] ?? '').length)) + 2,
  }))

  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Заявки')
  XLSX.writeFile(workbook, 'Заявки.xlsx', { bookType: 'xlsx', type: 'buffer' })
}
</script>

<style scoped>
:deep(.p-inputtext) {
  border: 1px solid rgb(226, 232, 240);
  color: rgb(15, 23, 42);
}
:deep(.p-inputtext::placeholder) {
  color: rgb(148, 163, 184);
}
:deep(.p-inputtext:focus) {
  border-color: rgb(37, 99, 235);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
  outline: none;
}
</style>
