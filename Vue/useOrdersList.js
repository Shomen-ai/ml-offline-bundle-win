import { ref, computed, watch } from 'vue'
import * as XLSX from 'xlsx-js-style'
import { formatDate, formatDateDetailed } from '@/components/Composables/formatDate'

/**
 * Логика списка заявок: поиск, фильтр по статусу, подгрузка, раскрытие, экспорт.
 * Разметка живёт в компонентах, здесь только данные.
 */
export function useOrdersList(props) {
  /* ---------- справочник статусов ---------- */

  const STATUS = {
    1: { label: 'Необработана', chip: 'bg-blue-100 text-blue-700' },
    2: { label: 'Доработка', chip: 'bg-amber-100 text-amber-700' },
    3: { label: 'Передана', chip: 'bg-violet-100 text-violet-700' },
    4: { label: 'В процессе', chip: 'bg-cyan-100 text-cyan-700' },
    5: { label: 'Завершена', chip: 'bg-emerald-100 text-emerald-700' },
  }

  const getStatusLabel = (state) => STATUS[state?.id]?.label ?? state?.state ?? 'Неизвестно'
  const statusClass = (id) => STATUS[id]?.chip ?? 'bg-slate-100 text-slate-600'

  /* ---------- состояние ---------- */

  const search = ref('')
  const activeStatus = ref(null)
  const visibleLimit = ref(15)
  const openIds = ref(new Set())

  const PAGE = 15

  /* ---------- плитки-счётчики ---------- */

  const statusTiles = computed(() => {
    const all = props.customers ?? []
    const countBy = (id) => all.filter((o) => o.state?.id === id).length

    return [
      { id: null, label: 'Все заявки', count: all.length, icon: 'pi-list', iconBg: 'bg-slate-100', iconColor: 'text-slate-600' },
      { id: 1, label: 'Необработанные', count: countBy(1), icon: 'pi-clock', iconBg: 'bg-blue-100', iconColor: 'text-blue-600' },
      { id: 2, label: 'На доработке', count: countBy(2), icon: 'pi-pencil', iconBg: 'bg-amber-100', iconColor: 'text-amber-600' },
      { id: 3, label: 'Переданные', count: countBy(3), icon: 'pi-send', iconBg: 'bg-violet-100', iconColor: 'text-violet-600' },
      { id: 4, label: 'В процессе', count: countBy(4), icon: 'pi-truck', iconBg: 'bg-cyan-100', iconColor: 'text-cyan-600' },
      { id: 5, label: 'Завершённые', count: countBy(5), icon: 'pi-check-circle', iconBg: 'bg-emerald-100', iconColor: 'text-emerald-600' },
    ]
  })

  function setStatus(id) {
    activeStatus.value = activeStatus.value === id ? null : id
  }

  /* ---------- фильтрация ---------- */

  const hasActiveFilters = computed(
    () => Boolean(search.value.trim()) || activeStatus.value !== null
  )

  const filteredCustomers = computed(() => {
    let result = props.customers ?? []

    if (activeStatus.value !== null) {
      result = result.filter((o) => o.state?.id === activeStatus.value)
    }

    const q = search.value.trim().toLowerCase()
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
          ...points(o).map((p) => p.comments),
        ]
          .map((v) => String(v ?? '').toLowerCase())
          .some((v) => v.includes(q))
      )
    }

    return result
  })

  const displayedCustomers = computed(() => filteredCustomers.value.slice(0, visibleLimit.value))

  const hasMore = computed(() => displayedCustomers.value.length < filteredCustomers.value.length)

  const loadMore = () => { visibleLimit.value += PAGE }

  watch(filteredCustomers, () => { visibleLimit.value = PAGE })

  function clearFilter() {
    search.value = ''
    activeStatus.value = null
  }

  /* ---------- раскрытие ---------- */

  const isOpen = (id) => openIds.value.has(id)

  function toggle(id) {
    const next = new Set(openIds.value)
    next.has(id) ? next.delete(id) : next.add(id)
    openIds.value = next
  }

  function collapseAll() {
    openIds.value = new Set()
  }

  /* ---------- разбор данных заявки ---------- */

  function shortFio(fio) {
    if (!fio) return '—'
    const [f, i, o] = String(fio).trim().split(/\s+/)
    return [f, i && `${i[0]}.`, o && `${o[0]}.`].filter(Boolean).join(' ')
  }

  function points(order) {
    return Array.isArray(order?.loading_and_delivery_points)
      ? order.loading_and_delivery_points
      : []
  }

  // "Местоположение:141 ПРОСК" -> "141 ПРОСК"
  function placeName(p) {
    return String(p?.comments ?? '').replace(/^Местоположение:\s*/i, '').trim()
  }

  function pointPlace(p) {
    const parts = []
    if (p.building) parts.push(`Корпус ${p.building}`)
    const place = placeName(p)
    if (place) parts.push(place)
    else if (p.department) parts.push(`Цех ${p.department}`)
    return parts.join(' · ') || 'место не указано'
  }

  function pointCoords(p) {
    if (!p.x_cord && !p.y_cord) return ''
    return `X-${p.x_cord ?? '—'} · Y-${p.y_cord ?? '—'}`
  }

  function pointDate(p) {
    if (!Array.isArray(p.date) || !p.date.length) return ''
    const from = safeFormatDate(p.date[0])
    const to = p.date[1] ? safeFormatDate(p.date[1]) : null
    if (from === '—') return ''
    return to && to !== '—' && to !== from ? `${from} — ${to}` : from
  }

  function routeSummary(order) {
    const list = points(order)
    if (!list.length) return 'Маршрут не указан'
    const name = (p) => placeName(p) || (p.building ? `Корпус ${p.building}` : '?')
    if (list.length <= 2) return list.map(name).join(' → ')
    return `${name(list[0])} → +${list.length - 2} → ${name(list.at(-1))}`
  }

  const getLoadingCount = (order) => points(order).filter((p) => p.type === 'loading').length
  const getUnloadingCount = (order) => points(order).filter((p) => p.type === 'unloading').length

  function getLoadingDates(order) {
    const first = points(order).find((p) => p.type === 'loading')
    if (!Array.isArray(first?.date) || !first.date.length) return '—'

    const dates = first.date
      .map((d) => {
        try {
          return d ? formatDateDetailed(d) : null
        } catch {
          return null
        }
      })
      .filter(Boolean)

    if (!dates.length) return '—'

    const single =
      !dates[1] || dates[0] === dates[1] || dates.some((d) => d.includes('01.01.1970'))

    return single ? `На ${dates[0]}` : `С ${dates[0]} по ${dates[1]}`
  }

  // comments заявки приходит как "Ключ: значение\nКлюч: значение"
  function cargo(order) {
    if (!order?.comments) return []
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

  function exportToExcel(fileName = 'Заявки.xlsx') {
    const cols = props.columns ?? []
    if (!cols.length) return

    const headers = cols.map((c) => c.header)
    const fields = cols.map((c) => c.field)

    const rows = filteredCustomers.value.map((row) =>
      fields.map((field) => field.split('.').reduce((acc, k) => acc?.[k], row) ?? '')
    )

    const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows])

    worksheet['!cols'] = headers.map((h, i) => ({
      wch: Math.max(10, String(h).length, ...rows.map((r) => String(r[i] ?? '').length)) + 2,
    }))

    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Заявки')
    XLSX.writeFile(workbook, fileName, { bookType: 'xlsx', type: 'buffer' })
  }

  return {
    // состояние
    search,
    activeStatus,
    // списки
    statusTiles,
    filteredCustomers,
    displayedCustomers,
    hasMore,
    hasActiveFilters,
    // действия
    setStatus,
    loadMore,
    clearFilter,
    isOpen,
    toggle,
    collapseAll,
    exportToExcel,
    // хелперы для шаблона
    getStatusLabel,
    statusClass,
    shortFio,
    points,
    pointPlace,
    pointCoords,
    pointDate,
    routeSummary,
    getLoadingCount,
    getUnloadingCount,
    getLoadingDates,
    cargo,
    safeFormatDate,
  }
}
