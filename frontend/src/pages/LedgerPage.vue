<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Delete, Plus } from '@element-plus/icons-vue'
import { fetchFinanceState, saveFinanceStateToDb } from '../lib/api'
import { currencyOptions, formatMoney } from '../lib/currency'
import { emptyLedgerEntry, ledgerCategoryOptions, sampleFinanceState, summarizeLedger } from '../lib/finance'

interface DayCard {
  date: string
  day: string
  weekday: string
  events: number
  income: number
  expense: number
}

const finance = ref(sampleFinanceState)
const selectedMonth = ref('')
const selectedDate = ref('')
const editorVisible = ref(false)
const loaded = ref(false)
const saveError = ref('')
const route = useRoute()

const monthOptions = computed(() => {
  const options = new Set<string>()
  const currentMonth = currentMonthLabel()
  for (const entry of finance.value.ledger) {
    const month = ledgerMonth(entry.date)
    if (month && month <= currentMonth) options.add(month)
  }
  for (const month of buildMonthOptionRange(48, 0)) {
    options.add(month)
  }
  if (selectedMonth.value && selectedMonth.value <= currentMonth) options.add(selectedMonth.value)
  return [...options].sort((a, b) => b.localeCompare(a))
})

const monthEntries = computed(() =>
  finance.value.ledger
    .filter((entry) => ledgerMonth(entry.date) === selectedMonth.value)
    .sort((a, b) => b.date.localeCompare(a.date)),
)
const ledgerCurrency = computed(() => {
  const monthRecord = finance.value.months.find((month) => month.label === selectedMonth.value)
  return monthRecord?.currency ?? finance.value.months[0]?.currency ?? 'CNY'
})

const ledger = computed(() => monthEntries.value.filter((entry) => entry.date === selectedDate.value))

const monthSummary = computed(() => summarizeLedger(monthEntries.value, ledgerCurrency.value))
const daySummary = computed(() => summarizeLedger(ledger.value, ledgerCurrency.value))
const monthDays = computed<DayCard[]>(() => buildMonthDays(selectedMonth.value))

watch(
  finance,
  async (nextState) => {
    if (!loaded.value) return
    try {
      await saveFinanceStateToDb(nextState)
      saveError.value = ''
    } catch (error) {
      saveError.value = error instanceof Error ? error.message : 'Failed to save finance database'
    }
  },
  { deep: true },
)

watch(monthOptions, (options) => {
  if (!selectedMonth.value || !options.includes(selectedMonth.value)) {
    selectedMonth.value = options[0] ?? currentMonthLabel()
  }
})

watch(
  [selectedMonth, monthDays],
  ([month, days]) => {
    if (!month) return
    const firstDay = days[0]?.day ?? '01'
    if (days.length === 0) {
      selectedDate.value = `${month}-01`
      return
    }
    if (!selectedDate.value || ledgerMonth(selectedDate.value) !== month) {
      selectedDate.value = `${month}-${firstDay}`
    } else if (!days.some((day) => day.date === selectedDate.value)) {
      selectedDate.value = `${month}-${firstDay}`
    }
  },
  { immediate: true },
)

onMounted(async () => {
  try {
    finance.value = await fetchFinanceState()
    saveError.value = ''
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : 'Failed to load finance database'
  } finally {
    const routeSelectedMonth = queryMonthLabel()
    if (routeSelectedMonth && monthOptions.value.includes(routeSelectedMonth)) {
      selectedMonth.value = routeSelectedMonth
    } else if (!selectedMonth.value) {
      selectedMonth.value = monthOptions.value[0] ?? currentMonthLabel()
    }
    loaded.value = true
  }
})

watch(
  () => route.query.month,
  () => {
    const routeSelectedMonth = queryMonthLabel()
    if (!routeSelectedMonth) return
    if (!monthOptions.value.includes(routeSelectedMonth)) return
    selectedMonth.value = routeSelectedMonth
  },
)

function addEntry(targetDate = selectedDate.value) {
  const date = targetDate || `${selectedMonth.value || currentMonthLabel()}-01`
  selectedDate.value = date
  const entry = emptyLedgerEntry(ledgerCurrency.value)
  entry.date = date
  finance.value.ledger.unshift(entry)
}

function openDateEditor(date: string) {
  selectedDate.value = date
  editorVisible.value = true
}

function removeEntry(id: string) {
  finance.value.ledger = finance.value.ledger.filter((entry) => entry.id !== id)
}

function ledgerMonth(date: string) {
  const match = /^(\d{4})-(\d{2})/.exec(date ?? '')
  if (!match) return ''
  return `${match[1]}-${match[2]}`
}

function queryMonthLabel() {
  const raw = route.query.month
  const month = Array.isArray(raw) ? raw[0] : raw
  if (typeof month !== 'string') return ''
  return /^\d{4}-\d{2}$/.test(month) ? month : ''
}

function currentMonthLabel() {
  return new Date().toISOString().slice(0, 7)
}

function buildMonthOptionRange(backwardMonths: number, forwardMonths: number) {
  const labels: string[] = []
  const today = new Date()
  const currentYear = today.getUTCFullYear()
  const currentMonth = today.getUTCMonth() + 1
  for (let offset = -forwardMonths; offset <= backwardMonths; offset += 1) {
    const total = currentYear * 12 + (currentMonth - 1) - offset
    const year = Math.floor(total / 12)
    const month = (total % 12) + 1
    labels.push(`${year}-${String(month).padStart(2, '0')}`)
  }
  return labels
}

function buildMonthDays(monthLabel: string): DayCard[] {
  const match = /^(\d{4})-(\d{2})$/.exec(monthLabel)
  if (!match) return []
  const year = Number(match[1])
  const month = Number(match[2])
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const cards: DayCard[] = []
  for (let day = 1; day <= days; day += 1) {
    const dayLabel = String(day).padStart(2, '0')
    const date = `${monthLabel}-${dayLabel}`
    const entries = monthEntries.value.filter((entry) => entry.date === date)
    const summary = summarizeLedger(entries, ledgerCurrency.value)
    cards.push({
      date,
      day: dayLabel,
      weekday: new Date(Date.UTC(year, month - 1, day)).toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' }),
      events: entries.length,
      income: summary.income,
      expense: summary.expense,
    })
  }
  return cards
}
</script>

<template>
  <section class="page-shell wide">
    <div class="page-head">
      <div>
        <p class="eyebrow">Daily Ledger</p>
        <h1>Income and expense log</h1>
        <p>Each month shows all dates. Click a date box to open the event editor window.</p>
      </div>
      <div class="actions">
        <el-select v-model="selectedMonth" class="month-select">
          <el-option v-for="month in monthOptions" :key="month" :label="month" :value="month" />
        </el-select>
      </div>
    </div>

    <el-alert v-if="saveError" :title="saveError" type="warning" show-icon :closable="false" class="page-alert" />

    <div class="sheet-summary">
      <span>Month {{ selectedMonth || '-' }}</span>
      <span>Income <b class="positive">{{ formatMoney(monthSummary.income, ledgerCurrency) }}</b></span>
      <span>Expense {{ formatMoney(monthSummary.expense, ledgerCurrency) }}</span>
      <span>Food {{ formatMoney(monthSummary.food, ledgerCurrency) }}</span>
      <span>Transport {{ formatMoney(monthSummary.transport, ledgerCurrency) }}</span>
      <span>Rent {{ formatMoney(monthSummary.rent, ledgerCurrency) }}</span>
    </div>

    <section class="panel ledger-calendar">
      <div class="section-head">
        <h2>{{ selectedMonth }} Dates</h2>
        <span>{{ monthEntries.length }} events in month</span>
      </div>
      <div class="ledger-calendar-grid">
        <div
          v-for="day in monthDays"
          :key="day.date"
          class="ledger-day"
          :class="{ active: day.date === selectedDate }"
          @click="openDateEditor(day.date)"
        >
          <div class="ledger-day-head">
            <strong>{{ day.day }}</strong>
            <small>{{ day.weekday }}</small>
          </div>
          <div class="ledger-day-stats">
            <span><em>Income</em> <b class="positive">{{ formatMoney(day.income, ledgerCurrency) }}</b></span>
            <span><em>Expense</em> <b class="negative">{{ formatMoney(day.expense, ledgerCurrency) }}</b></span>
          </div>
          <div class="ledger-day-footer">{{ day.events }} event{{ day.events === 1 ? '' : 's' }}</div>
        </div>
      </div>
    </section>

    <div class="sheet-summary">
      <span>Date {{ selectedDate || '-' }}</span>
      <span>Income <b class="positive">{{ formatMoney(daySummary.income, ledgerCurrency) }}</b></span>
      <span>Expense {{ formatMoney(daySummary.expense, ledgerCurrency) }}</span>
      <span>Food {{ formatMoney(daySummary.food, ledgerCurrency) }}</span>
      <span>Transport {{ formatMoney(daySummary.transport, ledgerCurrency) }}</span>
      <span>Rent {{ formatMoney(daySummary.rent, ledgerCurrency) }}</span>
    </div>

    <el-dialog v-model="editorVisible" class="ledger-editor-dialog" :title="`Events · ${selectedDate || '-'}`" width="min(1160px, 92vw)">
      <div class="sheet-summary">
        <span>Date {{ selectedDate || '-' }}</span>
        <span>Income <b class="positive">{{ formatMoney(daySummary.income, ledgerCurrency) }}</b></span>
        <span>Expense {{ formatMoney(daySummary.expense, ledgerCurrency) }}</span>
        <span>Food {{ formatMoney(daySummary.food, ledgerCurrency) }}</span>
        <span>Transport {{ formatMoney(daySummary.transport, ledgerCurrency) }}</span>
        <span>Rent {{ formatMoney(daySummary.rent, ledgerCurrency) }}</span>
      </div>
      <div class="ledger-editor-tools">
        <el-button type="primary" :icon="Plus" @click="addEntry(selectedDate)">Add Event</el-button>
      </div>
      <section class="sheet-panel">
        <el-table :data="ledger" size="large" class="data-table holdings-table" table-layout="fixed" empty-text="No events yet">
          <el-table-column label="Date" min-width="170">
            <template #default="{ row }">
              <span>{{ row.date }}</span>
            </template>
          </el-table-column>
          <el-table-column label="Category" min-width="170">
            <template #default="{ row }">
              <el-select v-model="row.category">
                <el-option v-for="category in ledgerCategoryOptions" :key="category" :label="category" :value="category" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="Amount" min-width="140" align="right">
            <template #default="{ row }"><el-input-number v-model="row.amount" :precision="2" :controls="false" /></template>
          </el-table-column>
          <el-table-column label="Currency" min-width="120">
            <template #default="{ row }">
              <el-select v-model="row.currency">
                <el-option v-for="currency in currencyOptions" :key="currency" :label="currency" :value="currency" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="Notes" min-width="260">
            <template #default="{ row }"><el-input v-model="row.notes" /></template>
          </el-table-column>
          <el-table-column width="72" fixed="right" align="center">
            <template #default="{ row }">
              <el-button :icon="Delete" circle aria-label="Delete row" @click="removeEntry(row.id)" />
            </template>
          </el-table-column>
        </el-table>
      </section>
    </el-dialog>
  </section>
</template>
