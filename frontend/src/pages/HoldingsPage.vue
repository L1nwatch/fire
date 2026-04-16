<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
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
const historyPage = ref(1)
const historyPageSize = 10

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
const chartModel = computed(() => {
  const points = chartPoints.value
  const width = 760
  const height = 260
  const pad = { top: 22, right: 22, bottom: 34, left: 54 }

  if (!points.length) {
    return {
      width,
      height,
      linePath: '',
      areaPath: '',
      points: [],
      min: 0,
      max: 0,
      first: undefined,
      latest: undefined,
      delta: 0,
      deltaPercent: 0,
    }
  }

  const normalized = points.map((point) => ({
    ...point,
    displayTotal: convertMoney(point.total, normalizeCurrency(point.currency), displayCurrency.value),
  }))
  const totals = normalized.map((point) => point.displayTotal)
  const min = Math.min(...totals)
  const max = Math.max(...totals)
  const range = max - min || 1
  const innerWidth = width - pad.left - pad.right
  const innerHeight = height - pad.top - pad.bottom
  const coords = normalized.map((point, index) => {
    const x = pad.left + (normalized.length === 1 ? innerWidth / 2 : (index / (normalized.length - 1)) * innerWidth)
    const y = pad.top + (1 - (point.displayTotal - min) / range) * innerHeight
    return { ...point, x, y }
  })
  const linePath = coords.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ')
  const first = coords[0]!
  const latest = coords[coords.length - 1]!
  const areaPath = `${linePath} L ${latest.x.toFixed(2)} ${height - pad.bottom} L ${first.x.toFixed(2)} ${height - pad.bottom} Z`
  const delta = latest.displayTotal - first.displayTotal

  return {
    width,
    height,
    linePath,
    areaPath,
    points: coords,
    min,
    max,
    first,
    latest,
    delta,
    deltaPercent: first.displayTotal ? (delta / first.displayTotal) * 100 : 0,
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

function percent(value: number) {
  return `${value.toFixed(1)}%`
}
</script>

<template>
  <section class="page-shell wide">
    <div class="page-head">
      <div>
        <p class="eyebrow">Investments</p>
        <h1>Manual asset snapshots</h1>
        <p>Record all investment assets on a date, copy the last snapshot forward, and track the trend.</p>
      </div>
      <div class="actions">
        <el-button @click="loadInvestments">Reload DB</el-button>
        <el-button type="primary" :icon="Plus" @click="addSnapshot">New From Latest</el-button>
      </div>
    </div>

    <el-alert v-if="saveError" :title="saveError" type="warning" show-icon :closable="false" class="page-alert" />

    <div class="investment-grid">
      <section class="panel trend-panel">
        <div class="section-head">
          <div>
            <h2>Investment Trend</h2>
            <span class="section-subtitle">{{ chartPoints.length }} snapshots</span>
          </div>
          <div class="trend-stat" :class="{ positive: chartModel.delta >= 0, negative: chartModel.delta < 0 }">
            <strong>{{ formatMoney(chartModel.delta, displayCurrency) }}</strong>
            <span>{{ percent(chartModel.deltaPercent) }}</span>
          </div>
        </div>
        <svg class="trend-chart" :viewBox="`0 0 ${chartModel.width} ${chartModel.height}`" role="img" aria-label="Investment total trend">
          <defs>
            <linearGradient id="investmentTrendFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stop-color="#1f7a63" stop-opacity="0.28" />
              <stop offset="100%" stop-color="#1f7a63" stop-opacity="0.02" />
            </linearGradient>
          </defs>
          <g class="chart-grid">
            <line x1="54" y1="22" x2="738" y2="22" />
            <line x1="54" y1="73" x2="738" y2="73" />
            <line x1="54" y1="124" x2="738" y2="124" />
            <line x1="54" y1="175" x2="738" y2="175" />
            <line x1="54" y1="226" x2="738" y2="226" />
          </g>
          <text x="54" y="17" class="chart-label">{{ formatMoney(chartModel.max, displayCurrency) }}</text>
          <text x="54" y="247" class="chart-label">{{ formatMoney(chartModel.min, displayCurrency) }}</text>
          <path v-if="chartModel.areaPath" :d="chartModel.areaPath" class="chart-area" />
          <path v-if="chartModel.linePath" :d="chartModel.linePath" class="chart-line" />
          <circle v-for="point in chartModel.points" :key="point.id" :cx="point.x" :cy="point.y" r="2.6" class="chart-point" />
          <circle v-if="chartModel.latest" :cx="chartModel.latest.x" :cy="chartModel.latest.y" r="5" class="chart-current-dot" />
        </svg>
        <div class="trend-labels">
          <span>{{ chartModel.first?.date ?? 'No data' }}</span>
          <strong>{{ chartModel.latest ? formatMoney(chartModel.latest.displayTotal, displayCurrency) : formatMoney(0, displayCurrency) }}</strong>
          <span>{{ chartModel.latest?.date ?? '' }}</span>
        </div>
      </section>

      <section class="panel">
        <div class="section-head">
          <h2>Latest Summary</h2>
          <span>{{ latestSnapshot?.date ?? '' }}</span>
        </div>
        <div class="report-stack" v-if="latestSnapshot">
          <div class="report-row">
            <span>Total assets</span>
            <strong>{{ formatMoney(latestTotal, latestSnapshot.currency) }}</strong>
          </div>
          <div class="report-row">
            <span>Rows</span>
            <strong>{{ latestSnapshot.items.length }}</strong>
          </div>
          <div class="report-row">
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
