<template>
  <div class="w-full space-y-3">
    <!-- ПАНЕЛЬ -->
    <div class="bg-white rounded-xl border border-slate-200 p-3">
      <div class="flex flex-wrap items-center gap-2">
        <div class="relative flex-1 min-w-[220px]">
          <i class="pi pi-search absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm" />
          <InputText
            v-model="h.search.value"
            placeholder="Номер, ФИО, подразделение, гараж, место…"
            class="w-full h-10 pl-10 pr-9 rounded-lg"
          />
          <button
            v-if="h.search.value"
            type="button"
            class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600"
            @click="h.search.value = ''"
          >
            <i class="pi pi-times text-xs" />
          </button>
        </div>

        <Button
          icon="pi pi-file-excel"
          label="Excel"
          class="h-10 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-lg"
          @click="h.exportToExcel()"
        />
        <Button
          v-if="h.hasActiveFilters.value"
          icon="pi pi-filter-slash"
          label="Сбросить"
          class="h-10 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-lg"
          @click="h.clearFilter()"
        />
      </div>
    </div>

    <!-- ПЛИТКИ СТАТУСОВ -->
    <div class="grid gap-2 grid-cols-[repeat(auto-fit,minmax(150px,1fr))]">
      <button
        v-for="tile in h.statusTiles.value"
        :key="tile.id ?? 'all'"
        type="button"
        class="flex items-center gap-3 px-4 h-14 rounded-xl border text-left transition-colors outline-none
               focus-visible:ring-2 focus-visible:ring-blue-500/40"
        :class="h.activeStatus.value === tile.id
          ? 'bg-blue-50 border-blue-300'
          : 'bg-white border-slate-200 hover:border-slate-300'"
        @click="h.setStatus(tile.id)"
      >
        <span class="shrink-0 size-8 rounded-lg grid place-items-center" :class="tile.iconBg">
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
    <div v-if="h.displayedCustomers.value.length" class="space-y-2">
      <OrderCard
        v-for="order in h.displayedCustomers.value"
        :key="order.id"
        :order="order"
        :open="h.isOpen(order.id)"
        :h="h"
        @toggle="h.toggle"
        @open="emit('openModal', $event)"
      >
        <template #actions="{ order: o }">
          <slot name="row-actions" :order="o" />
        </template>
      </OrderCard>

      <div v-if="h.hasMore.value" class="pt-1">
        <Button
          label="Показать ещё"
          icon="pi pi-angle-down"
          class="w-full h-11 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-xl"
          @click="h.loadMore()"
        />
        <p class="text-center text-xs text-slate-400 mt-2 tabular-nums">
          {{ h.displayedCustomers.value.length }} из {{ h.filteredCustomers.value.length }}
        </p>
      </div>
    </div>

    <!-- ПУСТО -->
    <div v-else class="bg-white rounded-xl border border-slate-200 py-12 px-4 text-center">
      <i class="pi pi-inbox text-3xl text-slate-300" />
      <p class="mt-3 text-slate-600">Заявок нет</p>
      <p class="mt-1 text-sm text-slate-400">
        {{ h.hasActiveFilters.value
          ? 'Измените условия поиска или сбросьте фильтры'
          : 'Здесь появятся поданные заявки' }}
      </p>
      <Button
        v-if="h.hasActiveFilters.value"
        label="Сбросить фильтры"
        class="mt-4 h-10 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-lg"
        @click="h.clearFilter()"
      />
    </div>
  </div>
</template>

<script setup>
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import OrderCard from './OrderCard.vue'
import { useOrdersList } from './useOrdersList'

const props = defineProps({
  columns: { type: Array, default: () => [] },
  customers: { type: Array, default: () => [] },
})

const emit = defineEmits(['openModal'])

const h = useOrdersList(props)
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

@media (pointer: coarse) {
  :deep(.p-button),
  :deep(.p-inputtext) {
    min-height: 2.75rem;
  }
}
</style>
