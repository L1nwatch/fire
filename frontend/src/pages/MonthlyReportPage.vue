<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import { emptyItem, emptyMonth, summarizeMonth, type FinancialMonth, type MoneySection } from '../lib/finance'
import { loadFinanceState, resetFinanceState, saveFinanceState } from '../lib/storage'

type MoneyItemKey = 'income' | 'expenses' | 'assets' | 'liabilities'

const finance = ref(loadFinanceState())
const selectedMonthId = ref(finance.value.months[0]?.id ?? '')
const selectedMonth = computed<FinancialMonth>(() => finance.value.months.find((month) => month.id === selectedMonthId.value) ?? finance.value.months[0] ?? emptyMonth())
const summary = computed(() => summarizeMonth(selectedMonth.value))

watch(
  finance,
  (nextState) => saveFinanceState(nextState),
  { deep: true },
)

function addMonth() {
  const month = emptyMonth()
  finance.value.months.unshift(month)
  selectedMonthId.value = month.id
}

function resetAll() {
  finance.value = resetFinanceState()
  selectedMonthId.value = finance.value.months[0]?.id ?? ''
}

function addItem(section: MoneySection) {
  selectedMonth.value[sectionKey(section)].push(emptyItem())
}

function removeItem(section: MoneySection, id: string) {
  const key = sectionKey(section)
  selectedMonth.value[key] = selectedMonth.value[key].filter((item) => item.id !== id)
}

function sectionItems(month: FinancialMonth, section: MoneySection) {
  return month[sectionKey(section)]
}

function sectionKey(section: MoneySection): MoneyItemKey {
  if (section === 'expense') return 'expenses'
  if (section === 'asset') return 'assets'
  if (section === 'liability') return 'liabilities'
  return 'income'
}

function money(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'CAD' }).format(value)
}
</script>

<template>
  <section class="page-shell wide">
    <div class="page-head">
      <div>
        <p class="eyebrow">Monthly Report</p>
        <h1>Income, spending, assets, liabilities</h1>
        <p>Use this like the monthly report workbook: four ledgers plus summary metrics.</p>
      </div>
      <div class="actions">
        <el-select v-model="selectedMonthId" class="month-select">
          <el-option v-for="month in finance.months" :key="month.id" :label="month.label" :value="month.id" />
        </el-select>
        <el-button @click="resetAll">Reset Sample</el-button>
        <el-button type="primary" :icon="Plus" @click="addMonth">Add Month</el-button>
      </div>
    </div>

    <div v-if="selectedMonth" class="workbook-layout">
      <section class="panel month-editor">
        <div class="month-fields">
          <label>
            <span>Month</span>
            <el-input v-model="selectedMonth.label" />
          </label>
          <label>
            <span>Currency</span>
            <el-input v-model="selectedMonth.currency" />
          </label>
          <label>
            <span>Passive income</span>
            <el-input-number v-model="selectedMonth.passiveIncome" :precision="2" controls-position="right" />
          </label>
        </div>
        <el-input v-model="selectedMonth.conclusion" type="textarea" :rows="2" placeholder="Conclusion" />
      </section>

      <section class="metric-grid workbook-metrics">
        <article class="metric-card">
          <span>Total income</span>
          <strong>{{ money(summary.totalIncome) }}</strong>
          <small>{{ money(summary.passiveIncome) }} passive</small>
        </article>
        <article class="metric-card">
          <span>Total spending</span>
          <strong class="negative">{{ money(summary.totalExpenses) }}</strong>
          <small>{{ money(summary.monthlyCashFlow) }} cash flow</small>
        </article>
        <article class="metric-card">
          <span>Net worth</span>
          <strong>{{ money(summary.netWorth) }}</strong>
          <small>{{ money(summary.totalLiabilities) }} liabilities</small>
        </article>
      </section>

      <section v-for="section in ['income', 'expense', 'asset', 'liability']" :key="section" class="panel">
        <div class="section-head">
          <h2>{{ section }}</h2>
          <el-button :icon="Plus" @click="addItem(section as MoneySection)">Add Row</el-button>
        </div>
        <el-table :data="sectionItems(selectedMonth, section as MoneySection)" size="large" class="data-table">
          <el-table-column label="Project" min-width="220">
            <template #default="{ row }"><el-input v-model="row.name" /></template>
          </el-table-column>
          <el-table-column label="Amount" min-width="160" align="right">
            <template #default="{ row }"><el-input-number v-model="row.amount" :precision="2" controls-position="right" /></template>
          </el-table-column>
          <el-table-column label="Notes" min-width="240">
            <template #default="{ row }"><el-input v-model="row.notes" /></template>
          </el-table-column>
          <el-table-column width="72" align="center">
            <template #default="{ row }">
              <el-button :icon="Delete" circle aria-label="Delete row" @click="removeItem(section as MoneySection, row.id)" />
            </template>
          </el-table-column>
        </el-table>
      </section>
    </div>
  </section>
</template>
