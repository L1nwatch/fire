<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { currencyHint, currencyOptions, displayCurrency, setDisplayCurrency, exchangeRates, exchangeRatesLoading, exchangeRatesNotice, refreshExchangeRates, type CurrencyCode } from './lib/currency'
import { useTheme } from './lib/theme'

const route = useRoute()
useTheme()

let ratesTimer: number | undefined
function refreshVisibleRates() {
  if (document.visibilityState === 'visible') void refreshExchangeRates()
}
onMounted(() => {
  void refreshExchangeRates()
  ratesTimer = window.setInterval(refreshVisibleRates, 60 * 60 * 1000)
  document.addEventListener('visibilitychange', refreshVisibleRates)
})
onBeforeUnmount(() => {
  window.clearInterval(ratesTimer)
  document.removeEventListener('visibilitychange', refreshVisibleRates)
})

const activePath = computed(() => {
  if (route.path.startsWith('/monthly')) return '/monthly'
  if (route.path.startsWith('/ledger')) return '/ledger'
  if (route.path.startsWith('/assets') || route.path.startsWith('/holdings')) return '/assets'
  if (route.path.startsWith('/investment') || route.path.startsWith('/forecast')) return '/investment'
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
        <el-menu-item index="/investment">Investment</el-menu-item>
      </el-menu>
    </aside>

    <main class="content">
      <div class="top-tools">
        <div class="currency-info">
          <span>{{ currencyHint }}</span>
          <small v-if="exchangeRates">
            <a href="https://www.bankofcanada.ca/rates/exchange/daily-exchange-rates/" target="_blank" rel="noopener noreferrer">Bank of Canada</a>
            · Daily reference · {{ exchangeRates.date }}
          </small>
        </div>
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
        <el-button size="small" :loading="exchangeRatesLoading" @click="refreshExchangeRates(true)">Refresh FX</el-button>
      </div>
      <el-alert v-if="exchangeRatesNotice" :title="exchangeRatesNotice" type="warning" :closable="false" show-icon class="exchange-rate-notice" />
      <router-view v-if="exchangeRates" />
      <div v-else class="panel" role="status">
        {{ exchangeRatesLoading ? 'Loading exchange rates…' : 'Refresh FX to load your financial overview.' }}
      </div>
    </main>
  </div>
</template>
