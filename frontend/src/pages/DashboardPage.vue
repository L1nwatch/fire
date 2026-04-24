<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchFinanceState, fetchInvestmentState, fetchPortfolioState } from '../lib/api'
import { convertMoney, displayCurrency, formatMoney, normalizeCurrency } from '../lib/currency'
import { emptyMonth, sampleFinanceState, summarizeReportMonth, type FinancialMonth } from '../lib/finance'
import {
  emptyInvestmentState,
  investmentItemAmount,
  normalizeInvestmentCategory,
  snapshotTotal,
  snapshotTotalByCategory,
  sortedSnapshots,
  type InvestmentItem,
} from '../lib/investments'

const finance = ref(sampleFinanceState)
const investments = ref(emptyInvestmentState())
const portfolio = ref(emptyInvestmentState())
const loadError = ref('')
const currentMonth = computed(() => finance.value.months[0] ?? emptyMonth())
const financeSummary = computed(() => summarizeFinanceMonth(currentMonth.value))
const latestInvestmentSnapshot = computed(() => sortedSnapshots(investments.value)[0])
const latestPortfolioSnapshot = computed(() => sortedSnapshots(portfolio.value)[0])
const investmentTotal = computed(() => snapshotTotal(latestInvestmentSnapshot.value, displayCurrency.value))
const portfolioInvestmentTotal = computed(() => snapshotTotal(latestPortfolioSnapshot.value, displayCurrency.value))
const investmentAvailable = computed(() => snapshotTotalByCategory(latestInvestmentSnapshot.value, displayCurrency.value, 'available'))
const investmentLocked = computed(() => snapshotTotalByCategory(latestInvestmentSnapshot.value, displayCurrency.value, 'locked'))
const barbellBreakdown = computed(() => {
  const snapshot = latestPortfolioSnapshot.value
  const items = snapshot?.items ?? []
  const entries = items
    .map((item) => {
      const sourceCurrency = normalizeCurrency(item.currency || snapshot?.currency || displayCurrency.value)
      const value = convertMoney(investmentItemAmount(item), sourceCurrency, displayCurrency.value)
      return {
        id: item.id,
        value,
        defensive: isDefensiveBarbellItem(item),
      }
    })
    .filter((entry) => Math.abs(entry.value) > 1e-9)

  const total = entries.reduce((sum, entry) => sum + entry.value, 0)
  const defensiveTotal = entries.filter((entry) => entry.defensive).reduce((sum, entry) => sum + entry.value, 0)
  const aggressiveTotal = entries.filter((entry) => !entry.defensive).reduce((sum, entry) => sum + entry.value, 0)
  return {
    total,
    defensive: {
      total: defensiveTotal,
      share: total ? defensiveTotal / total : 0,
    },
    aggressive: {
      total: aggressiveTotal,
      share: total ? aggressiveTotal / total : 0,
    },
  }
})
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
const assetGroups = computed(() => {
  const assets = [...(latestInvestmentSnapshot.value?.items ?? [])]
    .filter((asset) => asset.name || asset.amount)
    .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))

  const groups = [
    {
      key: 'available',
      label: 'Available',
      total: investmentAvailable.value,
      items: assets.filter((asset) => normalizeInvestmentCategory(asset.category) === 'Available'),
    },
    {
      key: 'locked',
      label: 'Locked',
      total: investmentLocked.value,
      items: assets.filter((asset) => normalizeInvestmentCategory(asset.category) === 'Locked'),
    },
  ]

  return groups.map((group) => ({
    ...group,
    visibleItems: group.items.slice(0, 8),
  }))
})

onMounted(async () => {
  try {
    const [financeState, investmentState, portfolioState] = await Promise.all([
      fetchFinanceState(),
      fetchInvestmentState(),
      fetchPortfolioState(),
    ])
    finance.value = financeState
    investments.value = investmentState
    portfolio.value = portfolioState
    loadError.value = ''
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Failed to load finance database'
  }
})

function percent(value: number) {
  return `${value.toFixed(1)}%`
}

function summarizeFinanceMonth(month: FinancialMonth) {
  return summarizeReportMonth(
    month,
    finance.value.ledger.filter((entry) => ledgerMonth(entry.date) === month.label),
  )
}

function ledgerMonth(date: string) {
  const match = /^(\d{4})-(\d{2})/.exec(date ?? '')
  if (!match) return ''
  return `${match[1]}-${match[2]}`
}

function roundPercent(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 10) / 10
}

function assetCurrency(asset: InvestmentItem) {
  return asset.currency || latestInvestmentSnapshot.value?.currency || displayCurrency.value
}

function isDefensiveBarbellItem(item: InvestmentItem) {
  const normalizedType = String(item.type || '').trim().toLowerCase()
  const normalizedName = String(item.name || '').trim().toLowerCase()
  const normalizedSymbol = String(item.symbol || '').trim().toLowerCase()
  if (normalizedType === 'cash') return true
  if (normalizedName.includes('cbil')) return true
  if (normalizedSymbol === 'cbil' || normalizedSymbol.startsWith('cbil.')) return true
  return false
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
    </div>

    <el-alert v-if="loadError" :title="loadError" type="warning" show-icon :closable="false" class="page-alert" />

    <div class="metric-grid">
      <article class="metric-card">
        <span>Net Worth</span>
        <strong>{{ formatMoney(investmentAvailable, displayCurrency) }}</strong>
        <small>{{ formatMoney(investmentAvailable, displayCurrency) }} available assets</small>
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
        <strong>{{ formatMoney(portfolioInvestmentTotal, displayCurrency) }}</strong>
        <small>{{ latestPortfolioSnapshot ? 'Current portfolio' : 'No investment snapshot' }}</small>
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
        <div class="report-stack" style="margin-top: 12px">
          <div class="report-row">
            <span>Barbell Left (Defensive)</span>
            <div class="barbell-row-values">
              <strong>{{ formatMoney(barbellBreakdown.defensive.total, displayCurrency) }}</strong>
              <small>{{ percent(barbellBreakdown.defensive.share * 100) }} of portfolio</small>
            </div>
          </div>
          <div class="report-row">
            <span>Barbell Right (Growth / Options)</span>
            <div class="barbell-row-values">
              <strong>{{ formatMoney(barbellBreakdown.aggressive.total, displayCurrency) }}</strong>
              <small>{{ percent(barbellBreakdown.aggressive.share * 100) }} of portfolio</small>
            </div>
          </div>
        </div>
      </section>
    </div>

    <section class="panel assets-panel">
      <div class="section-head">
        <h2>Assets</h2>
        <span>{{ latestInvestmentSnapshot?.date ?? currentMonth.label }}</span>
      </div>
      <div class="asset-groups">
        <div v-for="group in assetGroups" :key="group.key" class="asset-group" :class="group.key">
          <div class="asset-group-head">
            <div>
              <span>{{ group.label }}</span>
              <small>{{ group.items.length }} records</small>
            </div>
            <strong>{{ formatMoney(group.total, displayCurrency) }}</strong>
          </div>
          <div class="asset-list">
            <div v-for="asset in group.visibleItems" :key="asset.id" class="asset-row">
              <span>{{ asset.name }}</span>
              <strong>{{ formatMoney(asset.amount, assetCurrency(asset)) }}</strong>
            </div>
            <div v-if="!group.visibleItems.length" class="asset-row empty">
              <span>No records</span>
              <strong>{{ formatMoney(0, displayCurrency) }}</strong>
            </div>
            <router-link v-else-if="group.items.length > group.visibleItems.length" class="asset-row more" to="/assets">
              <span>{{ group.items.length - group.visibleItems.length }} more records</span>
              <strong>Open Assets</strong>
            </router-link>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>
