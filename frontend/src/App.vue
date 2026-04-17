<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { currencyHint, currencyOptions, displayCurrency, setDisplayCurrency, type CurrencyCode } from './lib/currency'

const route = useRoute()

const activePath = computed(() => {
  if (route.path.startsWith('/monthly')) return '/monthly'
  if (route.path.startsWith('/ledger')) return '/ledger'
  if (route.path.startsWith('/assets') || route.path.startsWith('/holdings')) return '/assets'
  if (route.path.startsWith('/forecast')) return '/forecast'
  return '/dashboard'
})
</script>

<template>
  <div class="app-frame">
    <aside class="side-nav">
      <div class="brand-block">
        <p class="brand">Fire</p>
        <p class="brand-sub">Financial independence tracking</p>
      </div>
      <el-menu :default-active="activePath" router class="menu">
        <el-menu-item index="/dashboard">Dashboard</el-menu-item>
        <el-menu-item index="/monthly">Monthly Report</el-menu-item>
        <el-menu-item index="/ledger">Daily Ledger</el-menu-item>
        <el-menu-item index="/assets">Assets</el-menu-item>
        <el-menu-item index="/forecast">Forecast</el-menu-item>
      </el-menu>
    </aside>

    <main class="content">
      <div class="top-tools">
        <span>{{ currencyHint }}</span>
        <el-button-group>
          <el-button
            v-for="currency in currencyOptions"
            :key="currency"
            size="small"
            :type="displayCurrency === currency ? 'primary' : 'default'"
            @click="setDisplayCurrency(currency as CurrencyCode)"
          >
            {{ currency }}
          </el-button>
        </el-button-group>
      </div>
      <router-view />
    </main>
  </div>
</template>
