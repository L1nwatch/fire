<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { fetchFinanceState, saveFinanceStateToDb } from '../lib/api'
import { formatMoney } from '../lib/currency'
import { emptyItem, emptyMonth, sampleFinanceState, summarizeMonth, type FinancialMonth, type MoneySection } from '../lib/finance'

type MoneyItemKey = 'income' | 'expenses' | 'assets' | 'liabilities'

const finance = ref(sampleFinanceState)
const selectedMonthId = ref(finance.value.months[0]?.id ?? '')
const loaded = ref(false)
const saveError = ref('')
const showEditor = ref(false)
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
const selectedMonth = computed<FinancialMonth>(() => months.value.find((month) => month.id === selectedMonthId.value) ?? latestMonth.value ?? emptyMonth())
const selectedSummary = computed(() => summarizeMonth(selectedMonth.value))
const latestSummary = computed(() => summarizeMonth(latestMonth.value ?? emptyMonth()))
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
    selectedMonthId.value = months.value[0]?.id ?? ''
    loaded.value = true
    saveError.value = ''
  } catch (error) {
    loaded.value = true
    saveError.value = error instanceof Error ? error.message : 'Failed to load finance database'
  }
}

function addMonth() {
  const month = emptyMonth()
  finance.value.months.unshift(month)
  selectedMonthId.value = month.id
  showEditor.value = true
}

function editMonth(id: string) {
  selectedMonthId.value = id
  showEditor.value = true
}

function editMonthRow(row: FinancialMonth) {
  editMonth(row.id)
}

function closeEditor() {
  showEditor.value = false
}

function deleteMonth() {
  if (!selectedMonth.value || finance.value.months.length <= 1) return
  const id = selectedMonth.value.id
  finance.value.months = finance.value.months.filter((month) => month.id !== id)
  selectedMonthId.value = months.value[0]?.id ?? ''
  showEditor.value = false
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
</script>

<template>
  <section class="page-shell wide">
    <div class="page-head">
      <div>
        <p class="eyebrow">Monthly Report</p>
        <h1>Income, spending, assets, liabilities</h1>
        <p>Track monthly cash flow, net worth, and report history from the workbook data.</p>
      </div>
      <div class="actions">
        <el-button type="primary" :icon="Plus" @click="addMonth">Add Month</el-button>
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
      <div ref="chartEl" class="trend-chart" role="img" aria-label="Monthly income spending and net worth trend"></div>

      <div class="asset-summary-strip monthly-summary-strip" v-if="latestMonth">
        <div class="asset-summary-item primary">
          <span>Total Income</span>
          <strong>{{ formatMoney(latestSummary.totalIncome, latestMonth.currency) }}</strong>
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
      <el-table :data="pagedMonths" size="large" class="data-table" table-layout="fixed" @row-click="editMonthRow">
        <el-table-column label="Month" min-width="130">
          <template #default="{ row }">
            <strong>{{ row.label }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="Income" min-width="150" align="right">
          <template #default="{ row }">{{ formatMoney(summarizeMonth(row).totalIncome, row.currency) }}</template>
        </el-table-column>
        <el-table-column label="Spending" min-width="150" align="right">
          <template #default="{ row }">
            <span class="negative">{{ formatMoney(summarizeMonth(row).totalExpenses, row.currency) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Cash Flow" min-width="150" align="right">
          <template #default="{ row }">
            <strong :class="{ positive: summarizeMonth(row).monthlyCashFlow >= 0, negative: summarizeMonth(row).monthlyCashFlow < 0 }">
              {{ formatMoney(summarizeMonth(row).monthlyCashFlow, row.currency) }}
            </strong>
          </template>
        </el-table-column>
        <el-table-column label="Savings Rate" min-width="130" align="right">
          <template #default="{ row }">
            <strong :class="{ positive: summarizeMonth(row).savingsRate >= 0, negative: summarizeMonth(row).savingsRate < 0 }">
              {{ percent(summarizeMonth(row).savingsRate) }}
            </strong>
          </template>
        </el-table-column>
        <el-table-column label="" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button @click.stop="editMonth(row.id)">Edit</el-button>
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

    <el-dialog
      v-model="showEditor"
      class="snapshot-dialog monthly-dialog"
      width="min(1180px, calc(100vw - 32px))"
      top="5vh"
      destroy-on-close
      append-to-body
    >
      <template #header>
        <div class="dialog-title" v-if="selectedMonth">
          <div>
            <span>Monthly Report Editor</span>
            <strong>{{ selectedMonth.label }}</strong>
          </div>
          <span>{{ formatMoney(selectedSummary.monthlyCashFlow, selectedMonth.currency) }}</span>
        </div>
      </template>

      <template v-if="selectedMonth">
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

        <section v-for="section in ['income', 'expense', 'asset', 'liability']" :key="section" class="monthly-editor-section">
          <div class="section-head">
            <h2>{{ section }}</h2>
            <el-button :icon="Plus" @click="addItem(section as MoneySection)">Add Row</el-button>
          </div>
          <el-table :data="sectionItems(selectedMonth, section as MoneySection)" size="large" class="data-table" table-layout="fixed" max-height="320">
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
      </template>

      <template #footer>
        <el-button :disabled="months.length <= 1" @click="deleteMonth">Delete Month</el-button>
        <el-button type="primary" @click="closeEditor">Done</el-button>
      </template>
    </el-dialog>
  </section>
</template>
