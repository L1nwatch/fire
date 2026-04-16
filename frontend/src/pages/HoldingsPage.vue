<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import {
  assetClasses,
  createHolding,
  holdingCost,
  holdingGainLoss,
  holdingGainLossPercent,
  holdingValue,
  riskLevels,
  summarizePortfolio,
  type Holding,
} from '../lib/portfolio'
import { loadHoldings, resetHoldings, saveHoldings } from '../lib/storage'

const holdings = ref<Holding[]>(loadHoldings())
const summary = computed(() => summarizePortfolio(holdings.value))

watch(
  holdings,
  (nextHoldings) => {
    saveHoldings(nextHoldings)
  },
  { deep: true },
)

function addHolding() {
  holdings.value.push(createHolding())
}

function removeHolding(id: string) {
  holdings.value = holdings.value.filter((holding) => holding.id !== id)
}

function restoreSampleData() {
  holdings.value = resetHoldings()
}

function money(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
}

function percent(value: number) {
  return `${value.toFixed(1)}%`
}
</script>

<template>
  <section class="page-shell wide">
    <div class="page-head">
      <div>
        <p class="eyebrow">Sheet</p>
        <h1>Investments</h1>
        <p>Update investment balances, asset class, cost basis, target weights, and notes.</p>
      </div>
      <div class="actions">
        <el-button @click="restoreSampleData">Reset Sample</el-button>
        <el-button type="primary" :icon="Plus" @click="addHolding">Add Row</el-button>
      </div>
    </div>

    <div class="sheet-summary">
      <span>Total {{ money(summary.marketValue) }}</span>
      <span>Basis {{ money(summary.costBasis) }}</span>
      <span :class="{ positive: summary.gainLoss >= 0, negative: summary.gainLoss < 0 }">
        Return {{ money(summary.gainLoss) }} / {{ percent(summary.gainLossPercent) }}
      </span>
    </div>

    <section class="sheet-panel">
      <el-table :data="holdings" size="large" class="data-table holdings-table" table-layout="fixed">
        <el-table-column label="Symbol" min-width="110">
          <template #default="{ row }">
            <el-input v-model="row.symbol" placeholder="VTI" />
          </template>
        </el-table-column>
        <el-table-column label="Name" min-width="190">
          <template #default="{ row }">
            <el-input v-model="row.name" placeholder="Holding name" />
          </template>
        </el-table-column>
        <el-table-column label="Class" min-width="150">
          <template #default="{ row }">
            <el-select v-model="row.assetClass">
              <el-option v-for="assetClass in assetClasses" :key="assetClass" :label="assetClass" :value="assetClass" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="Account" min-width="150">
          <template #default="{ row }">
            <el-input v-model="row.account" placeholder="Brokerage" />
          </template>
        </el-table-column>
        <el-table-column label="Qty" min-width="120" align="right">
          <template #default="{ row }">
            <el-input-number v-model="row.quantity" :min="0" :precision="4" controls-position="right" />
          </template>
        </el-table-column>
        <el-table-column label="Avg Cost" min-width="130" align="right">
          <template #default="{ row }">
            <el-input-number v-model="row.averageCost" :min="0" :precision="2" controls-position="right" />
          </template>
        </el-table-column>
        <el-table-column label="Price" min-width="130" align="right">
          <template #default="{ row }">
            <el-input-number v-model="row.marketPrice" :min="0" :precision="2" controls-position="right" />
          </template>
        </el-table-column>
        <el-table-column label="Value" min-width="120" align="right">
          <template #default="{ row }">{{ money(holdingValue(row)) }}</template>
        </el-table-column>
        <el-table-column label="Gain" min-width="120" align="right">
          <template #default="{ row }">
            <span :class="{ positive: holdingGainLoss(row) >= 0, negative: holdingGainLoss(row) < 0 }">
              {{ money(holdingGainLoss(row)) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="Gain %" min-width="100" align="right">
          <template #default="{ row }">{{ percent(holdingGainLossPercent(row)) }}</template>
        </el-table-column>
        <el-table-column label="Target %" min-width="120" align="right">
          <template #default="{ row }">
            <el-input-number v-model="row.targetWeight" :min="0" :max="100" :precision="1" controls-position="right" />
          </template>
        </el-table-column>
        <el-table-column label="Risk" min-width="130">
          <template #default="{ row }">
            <el-select v-model="row.risk">
              <el-option v-for="risk in riskLevels" :key="risk" :label="risk" :value="risk" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="Notes" min-width="220">
          <template #default="{ row }">
            <el-input v-model="row.notes" placeholder="Thesis, plan, reminder" />
          </template>
        </el-table-column>
        <el-table-column label="" width="72" fixed="right" align="center">
          <template #default="{ row }">
            <el-button :icon="Delete" circle aria-label="Delete row" @click="removeHolding(row.id)" />
          </template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>
