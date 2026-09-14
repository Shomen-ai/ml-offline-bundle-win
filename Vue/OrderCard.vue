<template>
  <article
    class="bg-white rounded-xl border overflow-hidden transition-colors"
    :class="open ? 'border-blue-300' : 'border-slate-200'"
  >
    <!-- СВЁРНУТАЯ СТРОКА -->
    <button
      type="button"
      class="w-full text-left px-4 py-3 flex items-center gap-4 outline-none transition-colors
             hover:bg-slate-50 focus-visible:bg-slate-50"
      :aria-expanded="open"
      @click="$emit('toggle', order.id)"
    >
      <!-- номер и заказчик -->
      <div class="w-36 shrink-0 min-w-0">
        <div class="font-semibold tabular-nums text-slate-900">{{ order.id }}</div>
        <div class="text-xs text-slate-500 truncate">
          {{ h.shortFio(order.fio) }}<template v-if="order.podr"> · {{ order.podr }}</template>
        </div>
      </div>

      <!-- статус -->
      <span
        class="shrink-0 px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap"
        :class="h.statusClass(order.state?.id)"
      >
        {{ h.getStatusLabel(order.state) }}
      </span>

      <!-- маршрут -->
      <div class="flex-1 min-w-0 hidden sm:block">
        <div class="text-sm text-slate-700 truncate">{{ h.routeSummary(order) }}</div>
        <div class="text-xs text-slate-400">
          {{ h.getLoadingCount(order) }} погр. · {{ h.getUnloadingCount(order) }} выгр.
        </div>
      </div>

      <!-- когда нужна машина -->
      <div class="w-48 shrink-0 hidden lg:block min-w-0">
        <div class="text-sm text-slate-700 truncate">{{ h.getLoadingDates(order) }}</div>
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
        :class="{ 'rotate-180': open }"
      />
    </button>

    <!-- на узком экране маршрут уезжает из шапки, показываем отдельной строкой -->
    <div
      v-if="!open"
      class="sm:hidden px-4 pb-3 -mt-1 text-sm text-slate-600 truncate"
    >
      {{ h.routeSummary(order) }}
    </div>

    <!-- РАСКРЫТИЕ -->
    <div v-if="open" class="border-t border-slate-100 bg-slate-50/60 px-4 py-4">
      <!-- маршрут -->
      <section class="mb-5">
        <h3 class="text-xs font-medium text-slate-500 mb-2">Маршрут</h3>

        <ol v-if="h.points(order).length" class="space-y-3">
          <li v-for="(p, i) in h.points(order)" :key="i" class="flex items-start gap-3">
            <span
              class="shrink-0 size-6 rounded-full grid place-items-center text-[11px] font-semibold text-white"
              :class="p.type === 'loading' ? 'bg-emerald-600' : 'bg-orange-500'"
            >{{ i + 1 }}</span>

            <div class="min-w-0 text-sm">
              <div class="text-slate-900">
                <span class="font-medium">
                  {{ p.type === 'loading' ? 'Погрузка' : 'Выгрузка' }}
                </span>
                <span class="text-slate-400"> · </span>{{ h.pointPlace(p) }}
              </div>

              <div v-if="h.pointDate(p)" class="text-xs text-slate-500 mt-0.5 tabular-nums">
                {{ h.pointDate(p) }}
              </div>
              <div v-if="h.pointCoords(p)" class="text-xs text-slate-400 mt-0.5 tabular-nums">
                {{ h.pointCoords(p) }}
              </div>
            </div>
          </li>
        </ol>

        <p v-else class="text-sm text-slate-400">Точки не указаны</p>
      </section>

      <!-- груз и контакты -->
      <div class="grid gap-x-8 gap-y-5 grid-cols-[repeat(auto-fit,minmax(260px,1fr))]">
        <section class="min-w-0">
          <h3 class="text-xs font-medium text-slate-500 mb-2">Груз</h3>
          <dl v-if="h.cargo(order).length" class="text-sm space-y-1">
            <div v-for="(row, i) in h.cargo(order)" :key="i" class="flex gap-3">
              <dt v-if="row.label" class="text-slate-500 w-40 shrink-0 truncate">
                {{ row.label }}
              </dt>
              <dd class="text-slate-900 min-w-0 break-words">{{ row.value }}</dd>
            </div>
          </dl>
          <p v-else class="text-sm text-slate-400">Не заполнено</p>
        </section>

        <section class="min-w-0">
          <h3 class="text-xs font-medium text-slate-500 mb-2">Контакты и исполнение</h3>
          <dl class="text-sm space-y-1">
            <div class="flex gap-3">
              <dt class="text-slate-500 w-40 shrink-0">Телефоны</dt>
              <dd class="text-slate-900 tabular-nums min-w-0 break-words">
                {{ [order.stat_number, order.mob_number].filter(Boolean).join(' · ') || '—' }}
              </dd>
            </div>
            <div class="flex gap-3">
              <dt class="text-slate-500 w-40 shrink-0">Водитель</dt>
              <dd class="text-slate-900">{{ order.driver?.fio ?? 'не назначен' }}</dd>
            </div>
            <div class="flex gap-3">
              <dt class="text-slate-500 w-40 shrink-0">Заявка создана</dt>
              <dd class="text-slate-900 tabular-nums">{{ h.safeFormatDate(order.created_at) }}</dd>
            </div>
            <div v-if="order.provide_car_time" class="flex gap-3">
              <dt class="text-slate-500 w-40 shrink-0">Машина подана</dt>
              <dd class="text-slate-900 tabular-nums">
                {{ h.safeFormatDate(order.provide_car_time) }}
              </dd>
            </div>
            <div v-if="order.complite_order_time" class="flex gap-3">
              <dt class="text-slate-500 w-40 shrink-0">Заявка закрыта</dt>
              <dd class="text-slate-900 tabular-nums">
                {{ h.safeFormatDate(order.complite_order_time) }}
              </dd>
            </div>
            <div v-if="order.dispatcher_comments" class="flex gap-3">
              <dt class="text-slate-500 w-40 shrink-0">От диспетчера</dt>
              <dd class="text-slate-900 min-w-0 break-words">{{ order.dispatcher_comments }}</dd>
            </div>
          </dl>
        </section>
      </div>

      <!-- действия -->
      <div class="mt-5 pt-4 border-t border-slate-200 flex flex-wrap gap-2">
        <Button
          icon="pi pi-eye"
          label="Открыть заявку"
          class="h-10 bg-blue-600 hover:bg-blue-700 text-white border-none rounded-lg"
          @click.stop="$emit('open', order)"
        />
        <slot name="actions" :order="order" />
      </div>
    </div>
  </article>
</template>

<script setup>
import Button from 'primevue/button'

defineProps({
  order: { type: Object, required: true },
  open: { type: Boolean, default: false },
  // объект хелперов из useOrdersList
  h: { type: Object, required: true },
})

defineEmits(['toggle', 'open'])
</script>
