<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import { emptyForecastEntry, forecastExpense, forecastNet } from '../lib/finance'
import { loadFinanceState, saveFinanceState } from '../lib/storage'

const finance = ref(loadFinanceState())
const forecast = computed(() => finance.value.forecast)

watch(
  finance,
  (nextState) => saveFinanceState(nextState),
  { deep: true },
)

function addEntry() {
  finance.value.forecast.push(emptyForecastEntry())
}

function removeEntry(id: string) {
  finance.value.forecast = finance.value.forecast.filter((entry) => entry.id !== id)
}

function money(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'CAD' }).format(value)
}
</script>

<template>
  <section class="page-shell wide">
    <div class="page-head">
      <div>
        <p class="eyebrow">Forecast</p>
        <h1>Income and expense planning</h1>
        <p>Plan tuition, rent, utilities, food, phone, other spending, and possible income.</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="addEntry">Add Forecast</el-button>
    </div>

    <section class="sheet-panel">
      <el-table :data="forecast" size="large" class="data-table holdings-table" table-layout="fixed">
        <el-table-column label="Event" min-width="180">
          <template #default="{ row }"><el-input v-model="row.event" /></template>
        </el-table-column>
        <el-table-column label="Year" min-width="110" align="right">
          <template #default="{ row }"><el-input-number v-model="row.year" :precision="0" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Period" min-width="150">
          <template #default="{ row }"><el-input v-model="row.period" /></template>
        </el-table-column>
        <el-table-column label="Months" min-width="110" align="right">
          <template #default="{ row }"><el-input-number v-model="row.months" :min="1" :precision="0" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Tuition" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.tuition" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Rent" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.rent" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Utilities" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.utilities" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Food" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.food" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Phone" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.phone" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Other" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.other" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Income" min-width="130" align="right">
          <template #default="{ row }"><el-input-number v-model="row.income" :precision="2" controls-position="right" /></template>
        </el-table-column>
        <el-table-column label="Net" min-width="130" align="right">
          <template #default="{ row }">
            <span :class="{ positive: forecastNet(row) >= 0, negative: forecastNet(row) < 0 }">{{ money(forecastNet(row)) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Expense" min-width="130" align="right">
          <template #default="{ row }">{{ money(forecastExpense(row)) }}</template>
        </el-table-column>
        <el-table-column label="Comment" min-width="240">
          <template #default="{ row }"><el-input v-model="row.comment" /></template>
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
