<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { fetchFinanceState, saveFinanceStateToDb } from '../lib/api'
import { formatMoney } from '../lib/currency'
import {
  emptyMonth,
  sampleFinanceState,
  summarizeLedger,
  summarizeMonth,
  type FinanceSummary,
  type FinancialMonth,
} from '../lib/finance'

const finance = ref(sampleFinanceState)
const loaded = ref(false)
const saveError = ref('')
const chartEl = ref<HTMLDivElement | null>(null)
const activeChartPoint = ref<MonthTrendPoint | null>(null)
const historyPage = ref(1)
const historyPageSize = 10
let chart: ECharts | null = null
const savingsRateChartMin = -100
const savingsRateChartMax = 100

interface MonthTrendPoint {
  id: string
  label: string
  currency: string
  income: number
  spending: number
  cashFlow: number
  savingsRate: number
  chartSavingsRate: number
  savingsRateCapped: boolean
}

const months = computed(() => [...finance.value.months].sort((a, b) => b.label.localeCompare(a.label)))
const pagedMonths = computed(() => {
  const start = (historyPage.value - 1) * historyPageSize
  return months.value.slice(start, start + historyPageSize)
})
const latestMonth = computed(() => months.value[0])
const latestSummary = computed(() => summarizeMonth(latestMonth.value ?? emptyMonth()))
const latestActiveIncome = computed(() => activeIncomeValue(latestSummary.value.totalIncome, latestSummary.value.passiveIncome))
const chartPoints = computed<MonthTrendPoint[]>(() =>
  [...finance.value.months]
    .sort((a, b) => a.label.localeCompare(b.label))
    .map((month) => {
      const summary = summarizeMonth(month)
      const chartSavingsRate = clampSavingsRate(summary.savingsRate)
      return {
        id: month.id,
        label: month.label,
        currency: month.currency,
        income: summary.totalIncome,
        spending: Math.abs(summary.totalExpenses),
        cashFlow: summary.monthlyCashFlow,
        savingsRate: summary.savingsRate,
        chartSavingsRate,
        savingsRateCapped: summary.savingsRate !== chartSavingsRate,
      }
    }),
)
const chartStats = computed(() => {
  const points = chartPoints.value
  const first = points[0]
  const latest = points[points.length - 1]
  const delta = first && latest ? latest.cashFlow - first.cashFlow : 0
  return {
    first,
    latest,
    delta,
    deltaPercent: first?.cashFlow ? (delta / Math.abs(first.cashFlow)) * 100 : 0,
  }
})

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

watch(months, (nextMonths) => {
  const maxPage = Math.max(1, Math.ceil(nextMonths.length / historyPageSize))
  if (historyPage.value > maxPage) {
    historyPage.value = maxPage
  }
})

watch(chartPoints, () => {
  syncActiveChartPoint()
  renderChart()
})

onMounted(async () => {
  await reloadFromDb()
  await nextTick()
  initChart()
  renderChart()
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
})

async function reloadFromDb() {
  try {
    finance.value = await fetchFinanceState()
    loaded.value = true
    saveError.value = ''
  } catch (error) {
    loaded.value = true
    saveError.value = error instanceof Error ? error.message : 'Failed to load finance database'
  }
}

function monthSummary(month: FinancialMonth) {
  const baseSummary = summarizeMonth(month)
  const ledgerSummary = summarizeLedger(
    finance.value.ledger.filter((entry) => ledgerMonth(entry.date) === month.label),
    month.currency,
  )
  const totalIncome = roundMoney(ledgerSummary.income)
  const totalExpenses = roundMoney(ledgerSummary.expense)
  const monthlyCashFlow = roundMoney(totalIncome + totalExpenses)
  const savingsRate = totalIncome ? roundPercent((monthlyCashFlow / totalIncome) * 100) : 0
  return {
    ...baseSummary,
    totalIncome,
    totalExpenses,
    monthlyCashFlow,
    savingsRate,
  } satisfies FinanceSummary
}

function activeIncomeForMonth(month: FinancialMonth) {
  const summary = monthSummary(month)
  return activeIncomeValue(summary.totalIncome, summary.passiveIncome)
}

function ledgerMonth(date: string) {
  const match = /^(\d{4})-(\d{2})/.exec(date ?? '')
  if (!match) return ''
  return `${match[1]}-${match[2]}`
}

function initChart() {
  if (!chartEl.value || chart) return
  chart = echarts.init(chartEl.value)
  chart.on('mouseover', (params) => {
    if (typeof params.dataIndex === 'number') {
      activeChartPoint.value = chartPoints.value[params.dataIndex] ?? chartStats.value.latest ?? null
    }
  })
  chart.on('globalout', () => {
    activeChartPoint.value = chartStats.value.latest ?? null
  })
}

function renderChart() {
  if (!chart) return
  syncActiveChartPoint()
  const points = chartPoints.value
  const maxMoneyValue = Math.max(0, ...points.map((point) => Math.max(point.income, point.spending)))
  const moneyAxisMax = maxMoneyValue > 0 ? maxMoneyValue * 1.2 : 1
  const moneyAxisCurrency = latestMonth.value?.currency ?? 'CNY'
  const option: EChartsOption = {
    animationDuration: 450,
    color: ['#1f7a63', '#d97432', '#2f6f9f'],
    grid: { left: 74, right: 62, top: 28, bottom: 50, containLabel: false },
    legend: {
      top: 0,
      right: 8,
      textStyle: { color: '#68716d', fontWeight: 700 },
      data: ['Income', 'Spending', 'Savings Rate'],
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        lineStyle: { color: '#7d8ca0', width: 1, type: 'dashed' },
      },
      formatter: (params) => {
        const items = Array.isArray(params) ? params : [params]
        const point = points[items[0]?.dataIndex ?? 0]
        if (!point) return ''
        activeChartPoint.value = point
        return [
          `<strong>${point.label}</strong>`,
          `Income: ${formatMoney(point.income, point.currency)}`,
          `Spending: ${formatMoney(point.spending, point.currency)}`,
          `Cash Flow: ${formatMoney(point.cashFlow, point.currency)}`,
          `Savings Rate: ${percent(point.savingsRate)}${point.savingsRateCapped ? ' (capped on chart)' : ''}`,
        ].join('<br/>')
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: points.map((point) => point.label),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#cfd8d3' } },
      axisLabel: { color: '#68716d', hideOverlap: true },
    },
    yAxis: [
      {
        type: 'value',
        scale: false,
        min: 0,
        max: moneyAxisMax,
        splitNumber: 5,
        axisLabel: {
          color: '#68716d',
          formatter: (value: number) => formatMoney(value, moneyAxisCurrency),
        },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: '#dce4df' } },
      },
      {
        type: 'value',
        scale: true,
        min: savingsRateChartMin,
        max: savingsRateChartMax,
        splitNumber: 5,
        axisLabel: {
          color: '#2f6f9f',
          formatter: (value: number) => percent(value),
        },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
      },
    ],
    series: [
      monthSeries('Income', points.map((point) => point.income), '#1f7a63'),
      monthSeries('Spending', points.map((point) => point.spending), '#d97432'),
      rateSeries('Savings Rate', points.map((point) => point.chartSavingsRate), '#2f6f9f'),
    ],
  }
  chart.setOption(option, true)
}

function monthSeries(name: string, data: number[], color: string) {
  return {
    type: 'line' as const,
    name,
    data,
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    showSymbol: false,
    emphasis: { focus: 'series' as const, scale: true },
    lineStyle: { width: 3, color },
  }
}

function rateSeries(name: string, data: number[], color: string) {
  return {
    type: 'line' as const,
    name,
    yAxisIndex: 1,
    data,
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    showSymbol: false,
    emphasis: { focus: 'series' as const, scale: true },
    lineStyle: { width: 2.5, color, type: 'dashed' as const },
  }
}

function resizeChart() {
  chart?.resize()
}

function syncActiveChartPoint() {
  const activeLabel = activeChartPoint.value?.label
  activeChartPoint.value = chartPoints.value.find((point) => point.label === activeLabel) ?? chartStats.value.latest ?? null
}

function percent(value: number) {
  return `${value.toFixed(1)}%`
}

function clampSavingsRate(value: number) {
  if (!Number.isFinite(value)) return 0
  return Math.min(savingsRateChartMax, Math.max(savingsRateChartMin, value))
}

function activeIncomeValue(totalIncome: number, passiveIncome: number) {
  return Math.round((totalIncome - passiveIncome) * 100) / 100
}

function roundMoney(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 100) / 100
}

function roundPercent(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 10) / 10
}
</script>

<template>
  <section class="page-shell wide">
    <div class="page-head">
      <div>
        <p class="eyebrow">Monthly Report</p>
        <h1>Income and spending</h1>
        <p>Monthly summary is derived from Daily Ledger records.</p>
      </div>
    </div>

    <el-alert v-if="saveError" :title="saveError" type="warning" show-icon :closable="false" class="page-alert" />

    <section class="panel trend-panel monthly-trend-panel">
      <div class="section-head">
        <div>
          <h2>Monthly Trend</h2>
          <span class="section-subtitle">
            {{ activeChartPoint?.label ?? chartStats.latest?.label ?? 'No data' }}
            <template v-if="activeChartPoint"> / Cash flow {{ formatMoney(activeChartPoint.cashFlow, activeChartPoint.currency) }}</template>
          </span>
        </div>
        <div class="trend-stat" :class="{ positive: chartStats.delta >= 0, negative: chartStats.delta < 0 }">
          <strong>{{ formatMoney(chartStats.delta, chartStats.latest?.currency ?? latestMonth?.currency ?? 'CNY') }}</strong>
          <span>{{ percent(chartStats.deltaPercent) }}</span>
        </div>
      </div>
      <div ref="chartEl" class="trend-chart" role="img" aria-label="Monthly income spending and savings rate trend"></div>

      <div class="asset-summary-strip monthly-summary-strip" v-if="latestMonth">
        <div class="asset-summary-item primary">
          <span>Total Income</span>
          <strong>{{ formatMoney(latestSummary.totalIncome, latestMonth.currency) }}</strong>
        </div>
        <div class="asset-summary-item">
          <span>Active Income</span>
          <strong>{{ formatMoney(latestActiveIncome, latestMonth.currency) }}</strong>
        </div>
        <div class="asset-summary-item">
          <span>Passive Income</span>
          <strong>{{ formatMoney(latestSummary.passiveIncome, latestMonth.currency) }}</strong>
        </div>
        <div class="asset-summary-item">
          <span>Total Spending</span>
          <strong class="negative">{{ formatMoney(latestSummary.totalExpenses, latestMonth.currency) }}</strong>
        </div>
        <div class="asset-summary-item">
          <span>Cash Flow</span>
          <strong :class="{ positive: latestSummary.monthlyCashFlow >= 0, negative: latestSummary.monthlyCashFlow < 0 }">
            {{ formatMoney(latestSummary.monthlyCashFlow, latestMonth.currency) }}
          </strong>
        </div>
        <div class="asset-summary-item">
          <span>Savings Rate</span>
          <strong>{{ percent(latestSummary.savingsRate) }}</strong>
        </div>
      </div>
    </section>

    <section class="panel snapshot-history">
      <div class="section-head">
        <h2>Report History</h2>
        <span>{{ months.length }} months</span>
      </div>
      <el-table :data="pagedMonths" row-key="id" size="large" class="data-table report-history-table" table-layout="fixed">
        <el-table-column label="Month" min-width="130">
          <template #default="{ row }">
            <strong>{{ row.label }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="Currency" min-width="110" align="center">
          <template #default="{ row }">
            <strong>{{ row.currency }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="Income" min-width="150" align="right">
          <template #default="{ row }">{{ formatMoney(monthSummary(row).totalIncome, row.currency) }}</template>
        </el-table-column>
        <el-table-column label="Active Income" min-width="150" align="right">
          <template #default="{ row }">{{ formatMoney(activeIncomeForMonth(row), row.currency) }}</template>
        </el-table-column>
        <el-table-column label="Passive Income" min-width="150" align="right">
          <template #default="{ row }">{{ formatMoney(monthSummary(row).passiveIncome, row.currency) }}</template>
        </el-table-column>
        <el-table-column label="Spending" min-width="150" align="right">
          <template #default="{ row }">
            <span class="negative">{{ formatMoney(monthSummary(row).totalExpenses, row.currency) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Cash Flow" min-width="150" align="right">
          <template #default="{ row }">
            <strong :class="{ positive: monthSummary(row).monthlyCashFlow >= 0, negative: monthSummary(row).monthlyCashFlow < 0 }">
              {{ formatMoney(monthSummary(row).monthlyCashFlow, row.currency) }}
            </strong>
          </template>
        </el-table-column>
        <el-table-column label="Savings Rate" min-width="130" align="right">
          <template #default="{ row }">
            <strong :class="{ positive: monthSummary(row).savingsRate >= 0, negative: monthSummary(row).savingsRate < 0 }">
              {{ percent(monthSummary(row).savingsRate) }}
            </strong>
          </template>
        </el-table-column>
        <el-table-column label="" width="130" fixed="right" align="center">
          <template #default="{ row }">
            <el-button tag="router-link" :to="{ name: 'ledger', query: { month: row.label } }">Open Ledger</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="months.length > historyPageSize"
        v-model:current-page="historyPage"
        class="history-pagination actions"
        layout="prev, pager, next"
        :page-size="historyPageSize"
        :total="months.length"
      />
    </section>
  </section>
</template>
