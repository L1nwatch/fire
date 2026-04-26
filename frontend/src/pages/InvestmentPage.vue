<script setup lang="ts">
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Delete, Plus, Refresh } from '@element-plus/icons-vue'
import { fetchLatestQuote, fetchMarketSentiment, fetchPortfolioState, savePortfolioStateToDb, type MarketSentimentSeries, type MarketSentimentState } from '../lib/api'
import { convertMoney, currencyOptions, displayCurrency, formatMoney, normalizeCurrency } from '../lib/currency'
import {
  createInvestmentItem,
  investmentItemCost,
  investmentItemProfit,
  investmentItemAmount,
  investmentCategoryOptions,
  investmentTypeOptions,
  isShareBasedType,
  snapshotTotal,
  snapshotTotalByCategory,
  type InvestmentItem,
  type InvestmentSnapshot,
} from '../lib/investments'

const CURRENT_PORTFOLIO_DATE = 'CURRENT'
const AUTO_REFRESH_MS = 2 * 60 * 1000
const BARBELL_ITEM_MIN_SHARE = 0.001

const portfolio = ref<InvestmentSnapshot>(createCurrentPortfolio())
const loaded = ref(false)
const saveError = ref('')
const quoteLoadingIds = ref<Record<string, boolean>>({})
const autoRefreshing = ref(false)
const sentimentLoading = ref(false)
const sentimentError = ref('')
const marketSentiment = ref<MarketSentimentState | null>(null)
const vxnChartEl = ref<HTMLDivElement | null>(null)
const fearGreedChartEl = ref<HTMLDivElement | null>(null)
const showEditor = ref(false)
const editorDraft = ref<InvestmentItem | null>(null)
const editingItemId = ref('')
const isCreatingItem = ref(false)
let autoRefreshTimer: number | null = null
let vxnChart: ECharts | null = null
let fearGreedChart: ECharts | null = null
const lastAutoRefreshAt = ref(0)

const totalAvailable = computed(() => snapshotTotalByCategory(portfolio.value, displayCurrency.value, 'available'))
const totalAll = computed(() => snapshotTotal(portfolio.value, displayCurrency.value))
const totalCost = computed(() =>
  round2(
    portfolio.value.items.reduce((sum, item) => {
      const itemCurrency = normalizeCurrency(item.currency || portfolio.value.currency || displayCurrency.value)
      return sum + convertMoney(investmentItemCost(item), itemCurrency, displayCurrency.value)
    }, 0),
  ),
)
const totalProfit = computed(() => round2(totalAll.value - totalCost.value))
const totalProfitPercent = computed(() => (Math.abs(totalCost.value) > 1e-9 ? (totalProfit.value / totalCost.value) * 100 : 0))
const vxnSeries = computed(() => marketSentiment.value?.vxn ?? null)
const fearGreedSeries = computed(() => marketSentiment.value?.fearGreed ?? null)
const vxnSignal = computed(() => {
  const value = vxnSeries.value?.latest
  if (!Number.isFinite(value)) {
    return { className: 'neutral', label: 'Waiting', detail: 'No VXN reading' }
  }
  if (Number(value) <= 22) {
    return { className: 'low', label: 'Low Vol', detail: 'VXN <= 22' }
  }
  if (Number(value) >= 30) {
    return { className: 'high', label: 'High Vol', detail: 'VXN >= 30' }
  }
  return { className: 'neutral', label: 'Neutral', detail: '22 < VXN < 30' }
})
const fearGreedSignal = computed(() => {
  const value = fearGreedSeries.value?.latest
  if (!Number.isFinite(value)) return 'Waiting'
  if (Number(value) <= 25) return 'Extreme Fear'
  if (Number(value) < 45) return 'Fear'
  if (Number(value) <= 55) return 'Neutral'
  if (Number(value) < 75) return 'Greed'
  return 'Extreme Greed'
})
const barbellBreakdown = computed(() => {
  const entries = portfolio.value.items
    .map((item) => {
      const sourceCurrency = normalizeCurrency(item.currency || portfolio.value.currency || displayCurrency.value)
      const value = convertMoney(investmentItemAmount(item), sourceCurrency, displayCurrency.value)
      return {
        id: item.id,
        label: item.name || item.symbol || 'Untitled',
        value,
        defensive: isDefensiveBarbellItem(item),
      }
    })
    .filter((entry) => Math.abs(entry.value) > 1e-9)

  const total = entries.reduce((sum, entry) => sum + entry.value, 0)
  const defensiveEntries = entries.filter((entry) => entry.defensive).sort((a, b) => b.value - a.value)
  const aggressiveEntries = entries.filter((entry) => !entry.defensive).sort((a, b) => b.value - a.value)
  const defensiveTotal = defensiveEntries.reduce((sum, entry) => sum + entry.value, 0)
  const aggressiveTotal = aggressiveEntries.reduce((sum, entry) => sum + entry.value, 0)
  const withShare = (entry: (typeof entries)[number]) => ({ ...entry, share: total ? entry.value / total : 0 })
  const visibleItems = (items: typeof entries) =>
    items
      .map(withShare)
      .filter((entry) => Math.abs(entry.share) >= BARBELL_ITEM_MIN_SHARE)

  return {
    total,
    defensive: {
      total: defensiveTotal,
      share: total ? defensiveTotal / total : 0,
      items: visibleItems(defensiveEntries),
    },
    aggressive: {
      total: aggressiveTotal,
      share: total ? aggressiveTotal / total : 0,
      items: visibleItems(aggressiveEntries),
    },
  }
})

watch(
  portfolio,
  async (nextPortfolio) => {
    if (!loaded.value) return
    try {
      await savePortfolioStateToDb({ snapshots: [sanitizePortfolio(nextPortfolio)] })
      saveError.value = ''
    } catch (error) {
      saveError.value = error instanceof Error ? error.message : 'Failed to save investment data'
    }
  },
  { deep: true },
)

onMounted(async () => {
  initSentimentCharts()
  window.addEventListener('resize', resizeSentimentCharts)
  void loadMarketSentiment()
  try {
    const state = await fetchPortfolioState()
    portfolio.value = state.snapshots[0] ? normalizePortfolio(state.snapshots[0]) : createCurrentPortfolio()
    saveError.value = ''
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : 'Failed to load investment data'
  } finally {
    loaded.value = true
  }
  await refreshAllQuotes({ silent: true })
  startAutoRefresh()
})

onBeforeUnmount(() => {
  stopAutoRefresh()
  window.removeEventListener('resize', resizeSentimentCharts)
  vxnChart?.dispose()
  fearGreedChart?.dispose()
})

async function loadMarketSentiment(options: { refresh?: boolean } = {}) {
  sentimentLoading.value = true
  try {
    const state = await fetchMarketSentiment(options)
    marketSentiment.value = state
    sentimentError.value = state.errors.length ? state.errors.join(' | ') : ''
  } catch (error) {
    sentimentError.value = error instanceof Error ? error.message : 'Failed to load market sentiment'
  } finally {
    sentimentLoading.value = false
    renderSentimentCharts()
  }
}

function addItem() {
  const newItem = createInvestmentItem(undefined, portfolio.value.currency || 'CAD')
  editorDraft.value = sanitizeItem(newItem)
  editingItemId.value = newItem.id
  isCreatingItem.value = true
  showEditor.value = true
}

function removeItem(id: string) {
  portfolio.value.items = portfolio.value.items.filter((item) => item.id !== id)
}

async function refreshQuote(item: InvestmentItem, options: { silent?: boolean } = {}) {
  if (!isShareBasedType(item.type)) return
  const enteredSymbol = (item.symbol || '').trim().toUpperCase()
  const lookupSymbol = (enteredSymbol || item.name || '').trim().toUpperCase()
  if (!lookupSymbol) {
    if (!options.silent) {
      saveError.value = 'Please enter a stock/ETF symbol first.'
    }
    return
  }
  const isOptionType = String(item.type || '').trim().toLowerCase() === 'option'
  const isOptionAlias = isOptionType && /^[A-Z0-9-]+\.(PUT|CALL)$/i.test(lookupSymbol)
  if (isOptionAlias) {
    const fallback = Number.isFinite(item.costBasis) && Math.abs(Number(item.costBasis)) > 1e-9
      ? round2(Number(item.costBasis))
      : 0
    item.unitPrice = fallback
    if (!options.silent) {
      saveError.value = 'Shorthand option symbols (e.g. QQQ.PUT) have no live quote feed; using cost basis as estimate.'
    }
    return
  }
  quoteLoadingIds.value = { ...quoteLoadingIds.value, [item.id]: true }
  try {
    const quote = await fetchLatestQuote(lookupSymbol)
    // Keep user's explicit symbol text (e.g. FBTC.CA) instead of replacing with provider aliases.
    item.symbol = enteredSymbol || quote.symbol
    item.unitPrice = round2(quote.price)
    const quoteCurrency = (quote.currency || '').toUpperCase()
    if (currencyOptions.includes(quoteCurrency as (typeof currencyOptions)[number])) {
      item.currency = quoteCurrency
    }
    if (!options.silent) {
      saveError.value = ''
    }
  } catch (error) {
    if (!options.silent) {
      saveError.value = error instanceof Error ? error.message : `Failed to fetch quote for ${lookupSymbol}`
    }
  } finally {
    quoteLoadingIds.value = { ...quoteLoadingIds.value, [item.id]: false }
  }
}

async function refreshAllQuotes(options: { silent?: boolean } = {}) {
  if (showEditor.value) return
  const targets = portfolio.value.items.filter((item) => isShareBasedType(item.type) && (item.symbol || item.name || '').trim())
  if (!targets.length) {
    return
  }
  autoRefreshing.value = true
  try {
    await Promise.all(targets.map((item) => refreshQuote(item, options)))
    lastAutoRefreshAt.value = Date.now()
  } finally {
    autoRefreshing.value = false
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  autoRefreshTimer = window.setInterval(() => {
    void refreshAllQuotes({ silent: true })
  }, AUTO_REFRESH_MS)
  document.addEventListener('visibilitychange', handleVisibilityChange)
}

function stopAutoRefresh() {
  if (autoRefreshTimer !== null) {
    window.clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
  document.removeEventListener('visibilitychange', handleVisibilityChange)
}

function handleVisibilityChange() {
  if (document.visibilityState !== 'visible') return
  if (Date.now() - lastAutoRefreshAt.value >= AUTO_REFRESH_MS) {
    void refreshAllQuotes({ silent: true })
  }
  void loadMarketSentiment()
}

function initSentimentCharts() {
  if (vxnChartEl.value && !vxnChart) {
    vxnChart = echarts.init(vxnChartEl.value)
  }
  if (fearGreedChartEl.value && !fearGreedChart) {
    fearGreedChart = echarts.init(fearGreedChartEl.value)
  }
}

function renderSentimentCharts() {
  initSentimentCharts()
  renderMarketChart(vxnChart, vxnSeries.value, '#6f5bb8', {
    min: undefined,
    max: undefined,
    markLines: [
      { yAxis: 22, name: 'Low' },
      { yAxis: 30, name: 'High' },
    ],
  })
  renderMarketChart(fearGreedChart, fearGreedSeries.value, '#d97432', { min: 0, max: 100 })
}

function renderMarketChart(
  chart: ECharts | null,
  series: MarketSentimentSeries | null,
  color: string,
  options: { min?: number; max?: number; markLines?: Array<{ yAxis: number; name: string }> } = {},
) {
  if (!chart || !series?.points.length) return
  const points = series.points
  const chartOption: EChartsOption = {
    animationDuration: 450,
    grid: { left: 36, right: 16, top: 16, bottom: 26 },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const item = Array.isArray(params) ? params[0] : params
        const point = points[item?.dataIndex ?? 0]
        if (!point) return ''
        return `${point.date}<br/><strong>${point.value.toFixed(1)}</strong>`
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: points.map((point) => point.date),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#d8dfec' } },
      axisLabel: {
        color: '#68716d',
        hideOverlap: true,
        formatter: (value: string) => value.slice(5),
      },
    },
    yAxis: {
      type: 'value',
      scale: options.min === undefined && options.max === undefined,
      min: options.min,
      max: options.max,
      splitNumber: 4,
      axisLabel: { color: '#68716d' },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#e2e8e4' } },
    },
    series: [
      {
        type: 'line',
        data: points.map((point) => point.value),
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        showSymbol: false,
        lineStyle: { width: 3, color },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: `${color}44` },
            { offset: 1, color: `${color}08` },
          ]),
        },
        markLine: options.markLines
          ? {
              symbol: 'none',
              label: { color: '#68716d', formatter: '{b}' },
              lineStyle: { type: 'dashed', color: '#8d98a8', width: 1 },
              data: options.markLines,
            }
          : undefined,
      },
    ],
  }
  chart.setOption(chartOption, true)
}

function resizeSentimentCharts() {
  vxnChart?.resize()
  fearGreedChart?.resize()
}

function openEditor(item: InvestmentItem) {
  editorDraft.value = sanitizeItem(item)
  editingItemId.value = item.id
  isCreatingItem.value = false
  showEditor.value = true
  void refreshEditorQuote({ silent: true })
}

function closeEditor() {
  showEditor.value = false
}

function onEditorClose() {
  applyEditorChanges()
}

function onEditorClosed() {
  resetEditorState()
}

function applyEditorChanges() {
  if (!editorDraft.value) return
  const nextItem = sanitizeItem(editorDraft.value)
  const existingIndex = portfolio.value.items.findIndex((item) => item.id === editingItemId.value)
  if (existingIndex >= 0) {
    portfolio.value.items.splice(existingIndex, 1, nextItem)
    return
  }
  if (isCreatingItem.value && hasMeaningfulItem(nextItem)) {
    portfolio.value.items.push(nextItem)
  }
}

function deleteFromEditor() {
  if (!editingItemId.value) {
    closeEditor()
    return
  }
  if (!isCreatingItem.value) {
    removeItem(editingItemId.value)
  }
  closeEditor()
}

async function refreshEditorQuote(options: { silent?: boolean } = {}) {
  if (!editorDraft.value) return
  await refreshQuote(editorDraft.value, options)
}

function resetEditorState() {
  editorDraft.value = null
  editingItemId.value = ''
  isCreatingItem.value = false
}

function normalizePortfolio(snapshot: InvestmentSnapshot): InvestmentSnapshot {
  return {
    id: snapshot.id || crypto.randomUUID(),
    date: CURRENT_PORTFOLIO_DATE,
    currency: snapshot.currency || 'CAD',
    notes: snapshot.notes || '',
    items: (snapshot.items || []).map((item) => createInvestmentItem(item, snapshot.currency || 'CAD')),
  }
}

function sanitizePortfolio(snapshot: InvestmentSnapshot): InvestmentSnapshot {
  return {
    ...normalizePortfolio(snapshot),
    items: snapshot.items.map((item) => sanitizeItem(item)),
  }
}

function sanitizeItem(item: InvestmentItem): InvestmentItem {
  const normalizedType = item.type || 'Other'
  const normalizedShares = Number.isFinite(item.shares) ? round2(item.shares || 0) : 0
  const normalizedUnitPrice = Number.isFinite(item.unitPrice) ? round2(item.unitPrice || 0) : 0
  const defaultCostBasis = isShareBasedType(normalizedType)
    ? normalizedUnitPrice
    : (Number.isFinite(item.amount) ? round2(item.amount || 0) : 0)
  return {
    id: item.id || crypto.randomUUID(),
    name: item.name || '',
    symbol: (item.symbol || '').toUpperCase().trim(),
    account: item.account || '',
    type: normalizedType,
    category: item.category || 'Available',
    shares: normalizedShares,
    unitPrice: normalizedUnitPrice,
    costBasis:
      Number.isFinite(item.costBasis) && Math.abs(Number(item.costBasis)) > 1e-9
        ? round2(item.costBasis || 0)
        : defaultCostBasis,
    amount: Number.isFinite(item.amount) ? round2(item.amount || 0) : round2(investmentItemAmount(item)),
    currency: item.currency || portfolio.value.currency || 'CAD',
    notes: item.notes || '',
  }
}

function createCurrentPortfolio(): InvestmentSnapshot {
  return {
    id: crypto.randomUUID(),
    date: CURRENT_PORTFOLIO_DATE,
    currency: 'CAD',
    notes: '',
    items: [],
  }
}

function round2(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 100) / 100
}

function rowProfit(item: InvestmentItem) {
  return round2(investmentItemProfit(item))
}

function rowProfitInDisplay(item: InvestmentItem) {
  const sourceCurrency = normalizeCurrency(item.currency || portfolio.value.currency || displayCurrency.value)
  return round2(convertMoney(rowProfit(item), sourceCurrency, displayCurrency.value))
}

function rowProfitPercent(item: InvestmentItem) {
  const cost = investmentItemCost(item)
  if (Math.abs(cost) <= 1e-9) return 0
  return (rowProfit(item) / cost) * 100
}

function rowProfitClass(item: InvestmentItem) {
  return rowProfitInDisplay(item) >= 0 ? 'positive' : 'negative'
}

function isDefensiveBarbellItem(item: InvestmentItem) {
  const normalizedType = String(item.type || '').trim().toLowerCase()
  const normalizedName = String(item.name || '').trim().toLowerCase()
  const normalizedSymbol = String(item.symbol || '').trim().toLowerCase()
  if (normalizedType === 'cash') return true
  if (normalizedName.includes('cbil')) return true
  if (normalizedSymbol === 'cbil' || normalizedSymbol.startsWith('cbil.')) return true
  return false
}

function hasMeaningfulItem(item: InvestmentItem) {
  if ((item.name || '').trim()) return true
  if ((item.symbol || '').trim()) return true
  if ((item.notes || '').trim()) return true
  if (Math.abs(Number(item.amount) || 0) > 1e-9) return true
  if (Math.abs(Number(item.shares) || 0) > 1e-9) return true
  if (Math.abs(Number(item.unitPrice) || 0) > 1e-9) return true
  if (Math.abs(Number(item.costBasis) || 0) > 1e-9) return true
  return false
}

function formatNumber(value: number | undefined) {
  const numeric = Number.isFinite(value) ? Number(value) : 0
  return numeric.toFixed(2)
}

function formatPercent(value: number) {
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${value.toFixed(2)}%`
}

function formatAllocation(value: number) {
  const normalized = Number.isFinite(value) ? Math.max(0, value) : 0
  return `${(normalized * 100).toFixed(1)}%`
}
</script>

<template>
  <section class="page-shell wide">
    <div class="page-head">
      <div>
        <p class="eyebrow">Investment</p>
        <h1>Current investment holdings</h1>
        <p>Track what you currently hold. No date snapshots on this page.</p>
      </div>
      <div class="actions">
        <span class="auto-refresh-hint">{{ autoRefreshing ? 'Refreshing quotes...' : 'Auto-refresh quotes every 2 min' }}</span>
        <el-button type="primary" :icon="Plus" @click="addItem">Add Holding</el-button>
      </div>
    </div>

    <el-alert v-if="saveError" :title="saveError" type="warning" show-icon :closable="false" class="page-alert" />

    <section class="market-sentiment-panel">
      <div class="section-head">
        <div>
          <h2>Market Sentiment</h2>
          <span class="section-subtitle">Nasdaq volatility and broad market fear/greed context.</span>
        </div>
        <el-button :icon="Refresh" :loading="sentimentLoading" plain @click="loadMarketSentiment({ refresh: true })">Refresh</el-button>
      </div>
      <el-alert v-if="sentimentError" :title="sentimentError" type="warning" show-icon :closable="false" class="sentiment-alert" />
      <div class="sentiment-grid">
        <article class="sentiment-card" :class="`vxn-${vxnSignal.className}`">
          <div class="sentiment-card-head">
            <div>
              <span>Cboe Nasdaq-100 Volatility Index</span>
              <strong>{{ vxnSeries?.latest === null || vxnSeries?.latest === undefined ? '-' : vxnSeries.latest.toFixed(2) }}</strong>
            </div>
            <div class="sentiment-badge" :class="vxnSignal.className">
              <strong>{{ vxnSignal.label }}</strong>
              <span>{{ vxnSignal.detail }}</span>
            </div>
          </div>
          <div class="sentiment-chart-wrap">
            <div ref="vxnChartEl" class="sentiment-chart" role="img" aria-label="VXN 3 month chart"></div>
            <span v-if="!vxnSeries?.points.length" class="sentiment-empty">No chart data</span>
          </div>
          <div class="sentiment-foot">
            <span>{{ vxnSeries?.latestDate ?? 'No data' }}</span>
            <span>{{ vxnSeries?.source ?? 'Provider unavailable' }}</span>
          </div>
        </article>

        <article class="sentiment-card">
          <div class="sentiment-card-head">
            <div>
              <span>CNN Fear & Greed Index</span>
              <strong>{{ fearGreedSeries?.latest === null || fearGreedSeries?.latest === undefined ? '-' : fearGreedSeries.latest.toFixed(1) }}</strong>
            </div>
            <div class="sentiment-badge neutral">
              <strong>{{ fearGreedSignal }}</strong>
              <span>0 fear / 100 greed</span>
            </div>
          </div>
          <div class="sentiment-chart-wrap">
            <div ref="fearGreedChartEl" class="sentiment-chart" role="img" aria-label="CNN Fear and Greed chart"></div>
            <span v-if="!fearGreedSeries?.points.length" class="sentiment-empty">No chart data</span>
          </div>
          <div class="sentiment-foot">
            <span>{{ fearGreedSeries?.latestDate ?? 'No data' }}</span>
            <span>{{ fearGreedSeries?.source ?? 'Provider unavailable' }}</span>
          </div>
        </article>
      </div>
    </section>

    <div class="asset-summary-strip monthly-summary-strip">
      <div class="asset-summary-item primary">
        <span>Available</span>
        <strong>{{ formatMoney(totalAvailable, displayCurrency) }}</strong>
      </div>
      <div class="asset-summary-item">
        <span>Market Value</span>
        <strong>{{ formatMoney(totalAll, displayCurrency) }}</strong>
      </div>
      <div class="asset-summary-item">
        <span>Cost Basis</span>
        <strong>{{ formatMoney(totalCost, displayCurrency) }}</strong>
      </div>
      <div class="asset-summary-item">
        <span>Profit / Loss</span>
        <strong :class="{ positive: totalProfit >= 0, negative: totalProfit < 0 }">{{ formatMoney(totalProfit, displayCurrency) }}</strong>
      </div>
      <div class="asset-summary-item">
        <span>Trend</span>
        <strong :class="{ positive: totalProfitPercent >= 0, negative: totalProfitPercent < 0 }">{{ formatPercent(totalProfitPercent) }}</strong>
      </div>
    </div>

    <section class="panel barbell-panel" style="margin-top: 14px">
      <div class="section-head">
        <div>
          <h2>Barbell Allocation</h2>
          <span class="section-subtitle">Defensive side (Cash + CBIL) vs growth side (equities/options and others).</span>
        </div>
      </div>
      <div class="asset-groups barbell-groups">
        <div class="asset-group available barbell-defensive">
          <div class="asset-group-head">
            <div>
              <span>Defensive</span>
              <small>{{ formatAllocation(barbellBreakdown.defensive.share) }} of portfolio</small>
            </div>
            <strong>{{ formatMoney(barbellBreakdown.defensive.total, displayCurrency) }}</strong>
          </div>
          <div class="asset-list barbell-list">
            <div v-for="item in barbellBreakdown.defensive.items" :key="item.id" class="asset-row barbell-item-row">
              <span>{{ item.label }}</span>
              <div class="barbell-row-values">
                <strong>{{ formatMoney(item.value, displayCurrency) }}</strong>
                <small>{{ formatAllocation(item.share) }}</small>
              </div>
            </div>
            <div v-if="!barbellBreakdown.defensive.items.length" class="asset-row barbell-item-row empty">No defensive holdings yet.</div>
          </div>
        </div>
        <div class="asset-group barbell-aggressive">
          <div class="asset-group-head">
            <div>
              <span>Growth / Options</span>
              <small>{{ formatAllocation(barbellBreakdown.aggressive.share) }} of portfolio</small>
            </div>
            <strong>{{ formatMoney(barbellBreakdown.aggressive.total, displayCurrency) }}</strong>
          </div>
          <div class="asset-list barbell-list">
            <div v-for="item in barbellBreakdown.aggressive.items" :key="item.id" class="asset-row barbell-item-row">
              <span>{{ item.label }}</span>
              <div class="barbell-row-values">
                <strong>{{ formatMoney(item.value, displayCurrency) }}</strong>
                <small>{{ formatAllocation(item.share) }}</small>
              </div>
            </div>
            <div v-if="!barbellBreakdown.aggressive.items.length" class="asset-row barbell-item-row empty">No growth/options holdings yet.</div>
          </div>
        </div>
      </div>
    </section>

    <section class="panel" style="margin-top: 14px">
      <div class="section-head" style="margin-bottom: 10px">
        <h2>Holdings</h2>
        <span class="section-subtitle">Click any row to edit. Changes are saved when you close the editor.</span>
      </div>

      <el-table
        :data="portfolio.items"
        size="large"
        class="data-table holdings-table investment-list-table"
        table-layout="fixed"
        empty-text="No holdings yet"
        @row-click="openEditor"
      >
        <el-table-column label="Asset" min-width="190">
          <template #default="{ row }">
            <strong>{{ row.name || '-' }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="Symbol" min-width="130">
          <template #default="{ row }">
            <span>{{ row.symbol || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Type" min-width="120">
          <template #default="{ row }">
            <span>{{ row.type || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Category" min-width="120">
          <template #default="{ row }">
            <span>{{ row.category || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Currency" width="110">
          <template #default="{ row }">
            <span>{{ row.currency || portfolio.currency }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Shares" min-width="120" align="right">
          <template #default="{ row }">
            <span v-if="isShareBasedType(row.type)">{{ formatNumber(row.shares) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="Market / Unit" min-width="140" align="right">
          <template #default="{ row }">
            <span v-if="isShareBasedType(row.type)">{{ formatNumber(row.unitPrice) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="Cost / Unit" min-width="130" align="right">
          <template #default="{ row }">
            <span v-if="isShareBasedType(row.type)">{{ formatNumber(row.costBasis) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="Amount" min-width="150" align="right">
          <template #default="{ row }">
            <span>{{ formatMoney(investmentItemAmount(row), row.currency || portfolio.currency) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="P/L Trend" min-width="170" align="right">
          <template #default="{ row }">
            <div class="pl-cell" :class="rowProfitClass(row)">
              <strong>{{ formatMoney(rowProfitInDisplay(row), displayCurrency) }}</strong>
              <small>{{ formatPercent(rowProfitPercent(row)) }}</small>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog
      v-model="showEditor"
      class="snapshot-dialog investment-editor-dialog"
      width="980px"
      destroy-on-close
      @close="onEditorClose"
      @closed="onEditorClosed"
    >
      <template #header>
        <div class="dialog-title">
          <div>
            <span>Investment Editor</span>
            <strong>{{ isCreatingItem ? 'New Holding' : 'Edit Holding' }}</strong>
          </div>
          <div class="dialog-summary" v-if="editorDraft">
            <span>Market {{ formatMoney(investmentItemAmount(editorDraft), editorDraft.currency || portfolio.currency) }}</span>
            <span :class="rowProfitClass(editorDraft)">P/L {{ formatMoney(rowProfitInDisplay(editorDraft), displayCurrency) }}</span>
          </div>
        </div>
      </template>

      <template v-if="editorDraft">
        <div class="month-fields">
          <label>
            <span>Asset</span>
            <el-input v-model="editorDraft.name" placeholder="AAPL, BTC, Cash, SPY..." />
          </label>
          <label>
            <span>Symbol</span>
            <el-input v-model="editorDraft.symbol" :disabled="!isShareBasedType(editorDraft.type)" placeholder="AAPL / FBTC.CA" @blur="refreshEditorQuote" />
          </label>
          <label>
            <span>Type</span>
            <el-select v-model="editorDraft.type" filterable allow-create default-first-option>
              <el-option v-for="itemType in investmentTypeOptions" :key="itemType" :label="itemType" :value="itemType" />
            </el-select>
          </label>
          <label>
            <span>Category</span>
            <el-select v-model="editorDraft.category" filterable allow-create default-first-option>
              <el-option v-for="category in investmentCategoryOptions" :key="category" :label="category" :value="category" />
            </el-select>
          </label>
          <label>
            <span>Currency</span>
            <el-select v-model="editorDraft.currency">
              <el-option v-for="currency in currencyOptions" :key="currency" :label="currency" :value="currency" />
            </el-select>
          </label>
          <label class="quote-action-wrap">
            <span>Quote</span>
            <el-input :model-value="isShareBasedType(editorDraft.type) ? formatNumber(editorDraft.unitPrice) : '-'" disabled />
          </label>
          <label>
            <span>Shares</span>
            <el-input-number v-if="isShareBasedType(editorDraft.type)" v-model="editorDraft.shares" :precision="2" :controls="false" />
            <el-input v-else model-value="-" disabled />
          </label>
          <label>
            <span>Market / Unit</span>
            <el-input v-if="isShareBasedType(editorDraft.type)" :model-value="formatNumber(editorDraft.unitPrice)" disabled />
            <el-input v-else model-value="-" disabled />
          </label>
          <label>
            <span>Cost / Unit</span>
            <el-input-number v-if="isShareBasedType(editorDraft.type)" v-model="editorDraft.costBasis" :precision="2" :controls="false" />
            <el-input v-else model-value="-" disabled />
          </label>
          <label>
            <span>Amount</span>
            <el-input-number v-if="!isShareBasedType(editorDraft.type)" v-model="editorDraft.amount" :precision="2" :controls="false" />
            <el-input v-else :model-value="formatMoney(investmentItemAmount(editorDraft), editorDraft.currency || portfolio.currency)" disabled />
          </label>
          <label>
            <span>Notes</span>
            <el-input v-model="editorDraft.notes" />
          </label>
        </div>
      </template>

      <template #footer>
        <div class="actions" style="width: 100%; justify-content: space-between">
          <el-button v-if="!isCreatingItem" :icon="Delete" type="danger" plain @click="deleteFromEditor">Delete</el-button>
          <span v-else></span>
          <el-button type="primary" @click="closeEditor">Done</el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>
