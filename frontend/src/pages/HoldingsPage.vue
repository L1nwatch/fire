<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { fetchInvestmentState, saveInvestmentStateToDb } from '../lib/api'
import { convertMoney, displayCurrency, formatMoney, normalizeCurrency } from '../lib/currency'
import {
  createInvestmentItem,
  createSnapshotFromPrevious,
  emptyInvestmentState,
  snapshotTotal,
  sortedSnapshots,
  trendPoints,
  type InvestmentSnapshot,
  type InvestmentState,
} from '../lib/investments'

const investments = ref<InvestmentState>(emptyInvestmentState())
const selectedSnapshotId = ref('')
const loaded = ref(false)
const saveError = ref('')
const showEditor = ref(false)
const chartEl = ref<HTMLDivElement | null>(null)
const activeChartPoint = ref<{ date: string; displayTotal: number } | null>(null)
const historyPage = ref(1)
const historyPageSize = 10
let chart: ECharts | null = null

const snapshots = computed(() => sortedSnapshots(investments.value))
const pagedSnapshots = computed(() => {
  const start = (historyPage.value - 1) * historyPageSize
  return snapshots.value.slice(start, start + historyPageSize)
})
const latestSnapshot = computed(() => snapshots.value[0])
const selectedSnapshot = computed<InvestmentSnapshot | undefined>(() => snapshots.value.find((snapshot) => snapshot.id === selectedSnapshotId.value) ?? latestSnapshot.value)
const latestTotal = computed(() => snapshotTotal(latestSnapshot.value))
const selectedTotal = computed(() => snapshotTotal(selectedSnapshot.value))
const chartPoints = computed(() => trendPoints(investments.value))
const chartSeries = computed(() =>
  chartPoints.value.map((point) => ({
    date: point.date,
    displayTotal: convertMoney(point.total, normalizeCurrency(point.currency), displayCurrency.value),
  })),
)
const chartStats = computed(() => {
  const points = chartSeries.value
  const first = points[0]
  const latest = points[points.length - 1]
  const delta = first && latest ? latest.displayTotal - first.displayTotal : 0
  return {
    first,
    latest,
    delta,
    deltaPercent: first?.displayTotal ? (delta / first.displayTotal) * 100 : 0,
  }
})

watch(
  investments,
  async (nextState) => {
    if (!loaded.value) return
    try {
      await saveInvestmentStateToDb(nextState)
      saveError.value = ''
    } catch (error) {
      saveError.value = error instanceof Error ? error.message : 'Failed to save investments'
    }
  },
  { deep: true },
)

watch(snapshots, (nextSnapshots) => {
  const maxPage = Math.max(1, Math.ceil(nextSnapshots.length / historyPageSize))
  if (historyPage.value > maxPage) {
    historyPage.value = maxPage
  }
})

onMounted(async () => {
  await loadInvestments()
  await nextTick()
  initChart()
  renderChart()
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
})

watch([chartSeries, displayCurrency], () => {
  renderChart()
})

async function loadInvestments() {
  try {
    investments.value = await fetchInvestmentState()
    if (!investments.value.snapshots.length) {
      investments.value.snapshots.push(createSnapshotFromPrevious())
    }
    selectedSnapshotId.value = snapshots.value[0]?.id ?? ''
    saveError.value = ''
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : 'Failed to load investments'
  } finally {
    loaded.value = true
  }
}

function addSnapshot() {
  const snapshot = createSnapshotFromPrevious(latestSnapshot.value)
  investments.value.snapshots.push(snapshot)
  selectedSnapshotId.value = snapshot.id
  showEditor.value = true
}

function editSnapshot(id: string) {
  selectedSnapshotId.value = id
  showEditor.value = true
}

function closeEditor() {
  showEditor.value = false
}

function deleteSnapshot() {
  if (!selectedSnapshot.value || investments.value.snapshots.length <= 1) return
  const id = selectedSnapshot.value.id
  investments.value.snapshots = investments.value.snapshots.filter((snapshot) => snapshot.id !== id)
  selectedSnapshotId.value = snapshots.value[0]?.id ?? ''
  showEditor.value = false
}

function addItem() {
  selectedSnapshot.value?.items.push(createInvestmentItem())
}

function removeItem(id: string) {
  if (!selectedSnapshot.value) return
  selectedSnapshot.value.items = selectedSnapshot.value.items.filter((item) => item.id !== id)
}

function initChart() {
  if (!chartEl.value || chart) return
  chart = echarts.init(chartEl.value)
  chart.on('mouseover', (params) => {
    if (typeof params.dataIndex === 'number') {
      activeChartPoint.value = chartSeries.value[params.dataIndex] ?? chartStats.value.latest ?? null
    }
  })
  chart.on('globalout', () => {
    activeChartPoint.value = chartStats.value.latest ?? null
  })
}

function renderChart() {
  if (!chart) return
  activeChartPoint.value = activeChartPoint.value ?? chartStats.value.latest ?? null
  const points = chartSeries.value
  const option: EChartsOption = {
    animationDuration: 450,
    color: ['#1f7a63'],
    grid: { left: 74, right: 28, top: 24, bottom: 50, containLabel: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        lineStyle: { color: '#7d8ca0', width: 1, type: 'dashed' },
        label: {
          show: true,
          formatter: (params) => String(params.value),
        },
      },
      formatter: (params) => {
        const item = Array.isArray(params) ? params[0] : params
        if (!item) return ''
        const point = points[item.dataIndex ?? 0]
        if (!point) return ''
        activeChartPoint.value = point
        return `${point.date}<br/><strong>${formatMoney(point.displayTotal, displayCurrency.value)}</strong>`
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: points.map((point) => point.date),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#cfd8d3' } },
      axisLabel: {
        color: '#68716d',
        hideOverlap: true,
        formatter: (value: string) => value.slice(0, 7),
      },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitNumber: 5,
      axisLabel: {
        color: '#68716d',
        formatter: (value: number) => formatMoney(value, displayCurrency.value),
      },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#dce4df' } },
    },
    series: [
      {
        type: 'line',
        name: 'Assets',
        data: points.map((point) => point.displayTotal),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: false,
        emphasis: { focus: 'series', scale: true },
        lineStyle: { width: 3, color: '#1f7a63' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(31, 122, 99, 0.3)' },
            { offset: 1, color: 'rgba(31, 122, 99, 0.02)' },
          ]),
        },
      },
    ],
  }
  chart.setOption(option, true)
}

function resizeChart() {
  chart?.resize()
}

function percent(value: number) {
  return `${value.toFixed(1)}%`
}
</script>

<template>
  <section class="page-shell wide">
    <div class="page-head">
      <div>
        <p class="eyebrow">Assets</p>
        <h1>Manual asset snapshots</h1>
        <p>Record all assets on a date, copy the last snapshot forward, and track the trend.</p>
      </div>
      <div class="actions">
        <el-button @click="loadInvestments">Reload DB</el-button>
        <el-button type="primary" :icon="Plus" @click="addSnapshot">New Asset Snapshot</el-button>
      </div>
    </div>

    <el-alert v-if="saveError" :title="saveError" type="warning" show-icon :closable="false" class="page-alert" />

    <div class="asset-overview">
      <section class="panel trend-panel">
        <div class="section-head">
          <div>
            <h2>Asset Trend</h2>
            <span class="section-subtitle">
              {{ activeChartPoint?.date ?? chartStats.latest?.date ?? 'No data' }}
              <template v-if="activeChartPoint"> / {{ formatMoney(activeChartPoint.displayTotal, displayCurrency) }}</template>
            </span>
          </div>
          <div class="trend-stat" :class="{ positive: chartStats.delta >= 0, negative: chartStats.delta < 0 }">
            <strong>{{ formatMoney(chartStats.delta, displayCurrency) }}</strong>
            <span>{{ percent(chartStats.deltaPercent) }}</span>
          </div>
        </div>
        <div ref="chartEl" class="trend-chart" role="img" aria-label="Investment total trend"></div>
        <div class="trend-labels">
          <span>{{ chartStats.first?.date ?? 'No data' }}</span>
          <strong>{{ activeChartPoint ? formatMoney(activeChartPoint.displayTotal, displayCurrency) : formatMoney(0, displayCurrency) }}</strong>
          <span>{{ chartStats.latest?.date ?? '' }}</span>
        </div>

        <div class="asset-summary-strip" v-if="latestSnapshot">
          <div class="asset-summary-item primary">
            <span>Latest total</span>
            <strong>{{ formatMoney(latestTotal, latestSnapshot.currency) }}</strong>
          </div>
          <div class="asset-summary-item">
            <span>Snapshot date</span>
            <strong>{{ latestSnapshot.date }}</strong>
          </div>
          <div class="asset-summary-item">
            <span>Asset rows</span>
            <strong>{{ latestSnapshot.items.length }}</strong>
          </div>
          <div class="asset-summary-item">
            <span>Currency</span>
            <strong>{{ latestSnapshot.currency }}</strong>
          </div>
        </div>
      </section>
    </div>

    <section class="panel snapshot-history">
      <div class="section-head">
        <h2>Snapshot History</h2>
        <span>{{ snapshots.length }} records</span>
      </div>
      <el-table :data="pagedSnapshots" size="large" class="data-table" table-layout="fixed">
        <el-table-column label="Date" min-width="140">
          <template #default="{ row }">
            <strong>{{ row.date }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="Total Assets" min-width="160" align="right">
          <template #default="{ row }">{{ formatMoney(snapshotTotal(row), row.currency) }}</template>
        </el-table-column>
        <el-table-column label="Currency" min-width="100">
          <template #default="{ row }">{{ row.currency }}</template>
        </el-table-column>
        <el-table-column label="Rows" min-width="90" align="right">
          <template #default="{ row }">{{ row.items.length }}</template>
        </el-table-column>
        <el-table-column label="Update Info" min-width="260">
          <template #default="{ row }">{{ row.notes || `${row.items.length} assets recorded` }}</template>
        </el-table-column>
        <el-table-column label="" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button @click="editSnapshot(row.id)">Edit</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="snapshots.length > historyPageSize"
        v-model:current-page="historyPage"
        class="history-pagination"
        layout="prev, pager, next, total"
        :page-size="historyPageSize"
        :total="snapshots.length"
      />
    </section>

    <section v-if="showEditor && selectedSnapshot" class="panel snapshot-editor">
      <div class="section-head">
        <h2>Snapshot Editor</h2>
        <span>{{ formatMoney(selectedTotal, selectedSnapshot.currency) }}</span>
      </div>

      <div class="month-fields">
        <label>
          <span>Date</span>
          <el-input v-model="selectedSnapshot.date" />
        </label>
        <label>
          <span>Currency</span>
          <el-select v-model="selectedSnapshot.currency">
            <el-option label="CAD" value="CAD" />
            <el-option label="CNY" value="CNY" />
            <el-option label="USD" value="USD" />
          </el-select>
        </label>
        <label>
          <span>Notes</span>
          <el-input v-model="selectedSnapshot.notes" />
        </label>
      </div>

      <div class="actions snapshot-actions">
        <el-button :icon="Plus" @click="addItem">Add Asset</el-button>
        <el-button :disabled="snapshots.length <= 1" @click="deleteSnapshot">Delete Snapshot</el-button>
        <el-button @click="closeEditor">Close Editor</el-button>
      </div>

      <el-table :data="selectedSnapshot.items" size="large" class="data-table holdings-table" table-layout="fixed">
        <el-table-column label="Asset" min-width="190">
          <template #default="{ row }">
            <el-input v-model="row.name" placeholder="WS-TFSA, IBKR, Cash" />
          </template>
        </el-table-column>
        <el-table-column label="Account" min-width="160">
          <template #default="{ row }">
            <el-input v-model="row.account" placeholder="Brokerage, bank, wallet" />
          </template>
        </el-table-column>
        <el-table-column label="Category" min-width="150">
          <template #default="{ row }">
            <el-input v-model="row.category" placeholder="ETF, cash, crypto" />
          </template>
        </el-table-column>
        <el-table-column label="Amount" min-width="160" align="right">
          <template #default="{ row }">
            <el-input-number v-model="row.amount" :precision="2" controls-position="right" />
          </template>
        </el-table-column>
        <el-table-column label="Notes" min-width="220">
          <template #default="{ row }">
            <el-input v-model="row.notes" />
          </template>
        </el-table-column>
        <el-table-column label="" width="72" fixed="right" align="center">
          <template #default="{ row }">
            <el-button :icon="Delete" circle aria-label="Delete row" @click="removeItem(row.id)" />
          </template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>
