<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import { fetchFinanceState, saveFinanceStateToDb } from '../lib/api'
import { emptyLedgerEntry, sampleFinanceState, summarizeLedger } from '../lib/finance'

const finance = ref(sampleFinanceState)
const ledger = computed(() => finance.value.ledger)
const summary = computed(() => summarizeLedger(ledger.value))
const loaded = ref(false)
const saveError = ref('')

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

onMounted(async () => {
  try {
    finance.value = await fetchFinanceState()
    saveError.value = ''
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : 'Failed to load finance database'
  } finally {
    loaded.value = true
  }
})

function addEntry() {
  finance.value.ledger.unshift(emptyLedgerEntry())
}

function removeEntry(id: string) {
  finance.value.ledger = finance.value.ledger.filter((entry) => entry.id !== id)
}

function money(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'CAD' }).format(value)
}
</script>

<template>
  <section class="page-shell wide">
    <div class="page-head">
      <div>
        <p class="eyebrow">Daily Ledger</p>
        <h1>Income and expense log</h1>
        <p>Track the same categories as the monthly date sheets: food, transport, shopping, bills, events, and rent.</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="addEntry">Add Day</el-button>
    </div>

    <el-alert v-if="saveError" :title="saveError" type="warning" show-icon :closable="false" class="page-alert" />

    <div class="sheet-summary">
      <span>Income {{ money(summary.income) }}</span>
      <span>Expense {{ money(summary.expense) }}</span>
      <span>Food {{ money(summary.food) }}</span>
      <span>Transport {{ money(summary.transport) }}</span>
      <span>Rent {{ money(summary.rent) }}</span>
    </div>

    <section class="sheet-panel">
      <el-table :data="ledger" size="large" class="data-table holdings-table" table-layout="fixed">
        <el-table-column label="Date" min-width="150">
          <template #default="{ row }"><el-input v-model="row.date" /></template>
        </el-table-column>
        <el-table-column label="Income" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.income" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Expense" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.expense" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Food" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.food" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Transport" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.transport" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Shopping" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.shopping" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Insurance" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.insurance" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Phone / tuition / net" min-width="170" align="right">
          <template #default="{ row }"><el-input-number v-model="row.telecom" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Utilities" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.utilities" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Event" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.event" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Shipping / rent" min-width="150" align="right">
          <template #default="{ row }"><el-input-number v-model="row.rent" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Notes" min-width="220">
          <template #default="{ row }"><el-input v-model="row.notes" /></template>
        </el-table-column>
        <el-table-column width="72" fixed="right" align="center">
          <template #default="{ row }">
            <el-button :icon="Delete" circle aria-label="Delete row" @click="removeEntry(row.id)" />
          </template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>
