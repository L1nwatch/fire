<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import { fetchInvestmentState, saveInvestmentStateToDb } from '../lib/api'
import { formatMoney } from '../lib/currency'
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

const snapshots = computed(() => sortedSnapshots(investments.value))
const latestSnapshot = computed(() => snapshots.value[0])
const selectedSnapshot = computed<InvestmentSnapshot | undefined>(() => snapshots.value.find((snapshot) => snapshot.id === selectedSnapshotId.value) ?? latestSnapshot.value)
const latestTotal = computed(() => snapshotTotal(latestSnapshot.value))
const selectedTotal = computed(() => snapshotTotal(selectedSnapshot.value))
const chartPoints = computed(() => trendPoints(investments.value))
const chartPolyline = computed(() => {
  const points = chartPoints.value
  if (!points.length) return ''
  const totals = points.map((point) => point.total)
  const min = Math.min(...totals)
  const max = Math.max(...totals)
  const range = max - min || 1
  return points
    .map((point, index) => {
      const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100
      const y = 90 - ((point.total - min) / range) * 75
      return `${x},${y}`
    })
    .join(' ')
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
}

function deleteSnapshot() {
  if (!selectedSnapshot.value || investments.value.snapshots.length <= 1) return
  const id = selectedSnapshot.value.id
  investments.value.snapshots = investments.value.snapshots.filter((snapshot) => snapshot.id !== id)
  selectedSnapshotId.value = snapshots.value[0]?.id ?? ''
}

function addItem() {
  selectedSnapshot.value?.items.push(createInvestmentItem())
}

function removeItem(id: string) {
  if (!selectedSnapshot.value) return
  selectedSnapshot.value.items = selectedSnapshot.value.items.filter((item) => item.id !== id)
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
        <el-select v-model="selectedSnapshotId" class="month-select">
          <el-option v-for="snapshot in snapshots" :key="snapshot.id" :label="snapshot.date" :value="snapshot.id" />
        </el-select>
        <el-button @click="loadInvestments">Reload DB</el-button>
        <el-button type="primary" :icon="Plus" @click="addSnapshot">New From Latest</el-button>
      </div>
    </div>

    <el-alert v-if="saveError" :title="saveError" type="warning" show-icon :closable="false" class="page-alert" />

    <div class="investment-grid">
      <section class="panel trend-panel">
        <div class="section-head">
          <h2>Trend</h2>
          <span>{{ chartPoints.length }} snapshots</span>
        </div>
        <svg class="trend-chart" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Investment total trend">
          <line x1="0" y1="90" x2="100" y2="90" class="chart-axis" />
          <polyline v-if="chartPolyline" :points="chartPolyline" class="chart-line" />
          <circle
            v-for="point in chartPoints"
            :key="point.id"
            :cx="chartPoints.length === 1 ? 50 : (chartPoints.indexOf(point) / (chartPoints.length - 1)) * 100"
            :cy="90 - ((point.total - Math.min(...chartPoints.map((p) => p.total))) / (Math.max(...chartPoints.map((p) => p.total)) - Math.min(...chartPoints.map((p) => p.total)) || 1)) * 75"
            r="1.6"
            class="chart-point"
          />
        </svg>
        <div class="trend-labels">
          <span>{{ chartPoints[0]?.date ?? 'No data' }}</span>
          <strong>{{ latestSnapshot ? formatMoney(latestTotal, latestSnapshot.currency) : formatMoney(0, 'CAD') }}</strong>
          <span>{{ chartPoints[chartPoints.length - 1]?.date ?? '' }}</span>
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

    <section v-if="selectedSnapshot" class="panel snapshot-editor">
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
