<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchFinanceState, fetchInvestmentState } from '../lib/api'
import { displayCurrency, formatMoney } from '../lib/currency'
import { emptyMonth, sampleFinanceState, summarizeMonth } from '../lib/finance'
import {
  emptyInvestmentState,
  normalizeInvestmentCategory,
  snapshotTotal,
  snapshotTotalByCategory,
  sortedSnapshots,
  type InvestmentItem,
} from '../lib/investments'

const finance = ref(sampleFinanceState)
const investments = ref(emptyInvestmentState())
const loadError = ref('')
const currentMonth = computed(() => finance.value.months[0] ?? emptyMonth())
const financeSummary = computed(() => summarizeMonth(currentMonth.value))
const latestInvestmentSnapshot = computed(() => sortedSnapshots(investments.value)[0])
const investmentTotal = computed(() => snapshotTotal(latestInvestmentSnapshot.value, displayCurrency.value))
const investmentAvailable = computed(() => snapshotTotalByCategory(latestInvestmentSnapshot.value, displayCurrency.value, 'available'))
const investmentLocked = computed(() => snapshotTotalByCategory(latestInvestmentSnapshot.value, displayCurrency.value, 'locked'))
const allocation = computed(() => {
  const total = investmentTotal.value
  return [
    { label: 'Available', value: investmentAvailable.value },
    { label: 'Locked', value: investmentLocked.value },
  ]
    .filter((row) => row.value > 0 || total > 0)
    .map((row) => ({
      ...row,
      weight: total ? roundPercent((row.value / total) * 100) : 0,
    }))
})
const topAssets = computed(() =>
  [...(latestInvestmentSnapshot.value?.items ?? [])]
    .filter((asset) => asset.name || asset.amount)
    .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))
    .slice(0, 12),
)

onMounted(async () => {
  try {
    const [financeState, investmentState] = await Promise.all([fetchFinanceState(), fetchInvestmentState()])
    finance.value = financeState
    investments.value = investmentState
    loadError.value = ''
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Failed to load finance database'
  }
})

function percent(value: number) {
  return `${value.toFixed(1)}%`
}

function roundPercent(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 10) / 10
}

function assetCurrency(asset: InvestmentItem) {
  return asset.currency || latestInvestmentSnapshot.value?.currency || displayCurrency.value
}
</script>

<template>
  <section class="page-shell">
    <div class="page-head">
      <div>
        <p class="eyebrow">Portfolio Monitor</p>
        <h1>Financial position</h1>
        <p>Monthly report, daily spending, asset balances, liabilities, and investments in one workspace.</p>
      </div>
      <el-button type="primary" tag="router-link" to="/monthly">Update Month</el-button>
    </div>

    <el-alert v-if="loadError" :title="loadError" type="warning" show-icon :closable="false" class="page-alert" />

    <div class="metric-grid">
      <article class="metric-card">
        <span>Net Worth</span>
        <strong>{{ formatMoney(financeSummary.netWorth, currentMonth.currency) }}</strong>
        <small>{{ formatMoney(financeSummary.totalAssets, currentMonth.currency) }} assets</small>
      </article>
      <article class="metric-card">
        <span>Monthly Cash Flow</span>
        <strong :class="{ positive: financeSummary.monthlyCashFlow >= 0, negative: financeSummary.monthlyCashFlow < 0 }">
          {{ formatMoney(financeSummary.monthlyCashFlow, currentMonth.currency) }}
        </strong>
        <small>{{ percent(financeSummary.savingsRate) }} savings rate</small>
      </article>
      <article class="metric-card">
        <span>Investment Value</span>
        <strong>{{ formatMoney(investmentTotal, displayCurrency) }}</strong>
        <small>{{ latestInvestmentSnapshot?.date ?? 'No asset snapshot' }}</small>
      </article>
    </div>

    <div class="dashboard-grid">
      <section class="panel">
        <div class="section-head">
          <h2>{{ currentMonth.label }} Report</h2>
          <span>{{ currentMonth.currency }}</span>
        </div>
        <div class="report-stack">
          <div class="report-row">
            <span>Total income</span>
            <strong>{{ formatMoney(financeSummary.totalIncome, currentMonth.currency) }}</strong>
          </div>
          <div class="report-row">
            <span>Total spending</span>
            <strong class="negative">{{ formatMoney(financeSummary.totalExpenses, currentMonth.currency) }}</strong>
          </div>
          <div class="report-row">
            <span>Passive income</span>
            <strong>{{ formatMoney(financeSummary.passiveIncome, currentMonth.currency) }}</strong>
          </div>
          <div class="report-row">
            <span>Liabilities</span>
            <strong class="negative">{{ formatMoney(financeSummary.totalLiabilities, currentMonth.currency) }}</strong>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="section-head">
          <h2>Investment Allocation</h2>
          <span>{{ displayCurrency }}</span>
        </div>
        <el-table :data="allocation" size="large" class="data-table">
          <el-table-column prop="label" label="Category" min-width="120" />
          <el-table-column label="Value" min-width="130" align="right">
            <template #default="{ row }">{{ formatMoney(row.value, displayCurrency) }}</template>
          </el-table-column>
          <el-table-column label="Weight" min-width="110" align="right">
            <template #default="{ row }">{{ percent(row.weight) }}</template>
          </el-table-column>
        </el-table>
      </section>

      <section class="panel">
        <div class="section-head">
          <h2>Assets</h2>
          <span>{{ latestInvestmentSnapshot?.date ?? currentMonth.label }}</span>
        </div>
        <div class="asset-list">
          <div v-for="asset in topAssets" :key="asset.id" class="asset-row">
            <span>{{ asset.name }} / {{ normalizeInvestmentCategory(asset.category) }}</span>
            <strong>{{ formatMoney(asset.amount, assetCurrency(asset)) }}</strong>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>
