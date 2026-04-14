<script setup lang="ts">
import { computed, ref } from 'vue'
import { allocationByAssetClass, summarizePortfolio, type RiskLevel } from '../lib/portfolio'
import { loadHoldings } from '../lib/storage'

const holdings = ref(loadHoldings())
const summary = computed(() => summarizePortfolio(holdings.value))
const allocation = computed(() => allocationByAssetClass(holdings.value))
const riskCounts = computed(() => {
  return holdings.value.reduce<Record<RiskLevel, number>>(
    (acc, holding) => {
      acc[holding.risk] += 1
      return acc
    },
    { Low: 0, Medium: 0, High: 0 },
  )
})

const topMovers = computed(() =>
  [...holdings.value]
    .filter((holding) => holding.symbol)
    .sort((a, b) => Math.abs(b.marketPrice - b.averageCost) * b.quantity - Math.abs(a.marketPrice - a.averageCost) * a.quantity)
    .slice(0, 5),
)

function money(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
}

function percent(value: number) {
  return `${value.toFixed(1)}%`
}
</script>

<template>
  <section class="page-shell">
    <div class="page-head">
      <div>
        <p class="eyebrow">Portfolio Monitor</p>
        <h1>Financial position</h1>
        <p>Track allocation, cash, cost basis, and investment drift from one sheet.</p>
      </div>
      <el-button type="primary" tag="router-link" to="/holdings">Update Holdings</el-button>
    </div>

    <div class="metric-grid">
      <article class="metric-card">
        <span>Total Value</span>
        <strong>{{ money(summary.marketValue) }}</strong>
        <small>{{ money(summary.investedValue) }} invested</small>
      </article>
      <article class="metric-card">
        <span>Gain / Loss</span>
        <strong :class="{ positive: summary.gainLoss >= 0, negative: summary.gainLoss < 0 }">{{ money(summary.gainLoss) }}</strong>
        <small>{{ percent(summary.gainLossPercent) }} total return</small>
      </article>
      <article class="metric-card">
        <span>Cost Basis</span>
        <strong>{{ money(summary.costBasis) }}</strong>
        <small>{{ money(summary.cashBalance) }} cash</small>
      </article>
    </div>

    <div class="dashboard-grid">
      <section class="panel">
        <div class="section-head">
          <h2>Allocation</h2>
          <span>Target drift</span>
        </div>
        <el-table :data="allocation" size="large" class="data-table">
          <el-table-column prop="label" label="Asset" min-width="120" />
          <el-table-column label="Value" min-width="130" align="right">
            <template #default="{ row }">{{ money(row.value) }}</template>
          </el-table-column>
          <el-table-column label="Weight" min-width="110" align="right">
            <template #default="{ row }">{{ percent(row.weight) }}</template>
          </el-table-column>
          <el-table-column label="Target" min-width="110" align="right">
            <template #default="{ row }">{{ percent(row.targetWeight) }}</template>
          </el-table-column>
          <el-table-column label="Drift" min-width="110" align="right">
            <template #default="{ row }">
              <span :class="{ positive: row.drift <= 0, warning: Math.abs(row.drift) > 5 }">{{ percent(row.drift) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="panel">
        <div class="section-head">
          <h2>Risk Mix</h2>
          <span>{{ holdings.length }} holdings</span>
        </div>
        <div class="risk-list">
          <div class="risk-row low">
            <span>Low</span>
            <strong>{{ riskCounts.Low }}</strong>
          </div>
          <div class="risk-row medium">
            <span>Medium</span>
            <strong>{{ riskCounts.Medium }}</strong>
          </div>
          <div class="risk-row high">
            <span>High</span>
            <strong>{{ riskCounts.High }}</strong>
          </div>
        </div>

        <h2 class="subhead">Largest Moves</h2>
        <div class="mover-list">
          <div v-for="holding in topMovers" :key="holding.id" class="mover-row">
            <span>{{ holding.symbol }}</span>
            <strong>{{ money((holding.marketPrice - holding.averageCost) * holding.quantity) }}</strong>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>
