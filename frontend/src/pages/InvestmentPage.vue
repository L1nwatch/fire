<script setup lang="ts">
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Delete, Plus, Refresh } from '@element-plus/icons-vue'
import { fetchLatestQuote, fetchMarketSentiment, fetchPortfolioState, savePortfolioStateToDb, type MarketSentimentSeries, type MarketSentimentState } from '../lib/api'
import { chartThemeColors } from '../lib/chartTheme'
import { convertMoney, currencyOptions, displayCurrency, formatMoney, normalizeCurrency } from '../lib/currency'
import {
  createInvestmentItem,
  investmentItemCost,
  investmentItemProfit,
  investmentItemAmount,
  investmentItemLookupSymbol,
  investmentItemMergeSymbol,
  investmentCategoryOptions,
  investmentTypeOptions,
  isShareBasedType,
  snapshotTotal,
  snapshotTotalByCategory,
  type InvestmentItem,
  type InvestmentSnapshot,
} from '../lib/investments'
import { useTheme } from '../lib/theme'

const CURRENT_PORTFOLIO_DATE = 'CURRENT'
const AUTO_REFRESH_MS = 2 * 60 * 1000
const { isDark } = useTheme()

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
const allocationChartEl = ref<HTMLDivElement | null>(null)
const showEditor = ref(false)
const editorViewportStyle = ref<Record<string, string>>({})
const editorDraft = ref<InvestmentItem | null>(null)
const editingItemId = ref('')
const isCreatingItem = ref(false)
let autoRefreshTimer: number | null = null
let vxnChart: ECharts | null = null
let fearGreedChart: ECharts | null = null
let allocationChart: ECharts | null = null
const lastAutoRefreshAt = ref(0)

const totalAvailable = computed(() => snapshotTotalByCategory(portfolio.value, displayCurrency.value, 'available'))
const totalAll = computed(() => snapshotTotal(portfolio.value, displayCurrency.value))
const totalCost = computed(() =>
  round2(
    portfolio.value.items.filter(hasProfitTrend).reduce((sum, item) => {
      const itemCurrency = normalizeCurrency(item.currency || portfolio.value.currency || displayCurrency.value)
      return sum + convertMoney(investmentItemCost(item), itemCurrency, displayCurrency.value)
    }, 0),
  ),
)
const totalProfit = computed(() =>
  round2(
    portfolio.value.items.filter(hasProfitTrend).reduce((sum, item) => {
      const itemCurrency = normalizeCurrency(item.currency || portfolio.value.currency || displayCurrency.value)
      return sum + convertMoney(rowProfit(item), itemCurrency, displayCurrency.value)
    }, 0),
  ),
)
const totalProfitPercent = computed(() => (Math.abs(totalCost.value) > 1e-9 ? (totalProfit.value / totalCost.value) * 100 : 0))
const sortedHoldingItems = computed(() =>
  [...portfolio.value.items].sort((a, b) => {
    const aValue = convertMoney(investmentItemAmount(a), rowCurrency(a), displayCurrency.value)
    const bValue = convertMoney(investmentItemAmount(b), rowCurrency(b), displayCurrency.value)
    return bValue - aValue || (a.name || a.symbol || '').localeCompare(b.name || b.symbol || '')
  }),
)
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
const allocationEntries = computed(() => {
  const mergedEntries = new Map<string, {
    id: string
    label: string
    name: string
    type: string
    value: number
    cost: number
    count: number
    hasTrend: boolean
  }>()

  portfolio.value.items.forEach((item) => {
    const value = Math.max(0, rowValueInDisplay(item))
    if (value <= 1e-9) return
    const cost = convertMoney(investmentItemCost(item), rowCurrency(item), displayCurrency.value)
    const mergeSymbol = investmentItemMergeSymbol(item)
    const key = mergeSymbol || item.id
    const existing = mergedEntries.get(key)
    if (existing) {
      existing.value += value
      existing.cost += cost
      existing.count += 1
      existing.hasTrend = existing.hasTrend || hasProfitTrend(item)
      if (existing.type.toLowerCase() === 'cash' && String(item.type || '').toLowerCase() !== 'cash') {
        existing.type = item.type || 'Other'
      }
      return
    }
    mergedEntries.set(key, {
      id: item.id,
      label: mergeSymbol || positionSymbol(item),
      name: item.name || positionSymbol(item),
      type: item.type || 'Other',
      value,
      cost,
      count: 1,
      hasTrend: hasProfitTrend(item),
    })
  })

  const entries = [...mergedEntries.values()]
    .map((entry) => {
      const profit = entry.value - entry.cost
      return {
        ...entry,
        profit,
        profitPercent: entry.hasTrend && Math.abs(entry.cost) > 1e-9 ? (profit / entry.cost) * 100 : 0,
      }
    })
    .sort((a, b) => b.value - a.value)
  const total = entries.reduce((sum, entry) => sum + entry.value, 0)
  return entries.map((entry) => ({ ...entry, share: total ? entry.value / total : 0 }))
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

watch(allocationEntries, () => renderAllocationChart(), { deep: true, flush: 'post' })

onMounted(async () => {
  initCharts()
  window.addEventListener('resize', resizeCharts)
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
  window.removeEventListener('resize', resizeCharts)
  vxnChart?.dispose()
  fearGreedChart?.dispose()
  allocationChart?.dispose()
})

watch(isDark, () => {
  renderSentimentCharts()
  renderAllocationChart()
})

// Mobile keyboards resize the visual viewport without always changing 100dvh.
watch(showEditor, (visible, _previous, onCleanup) => {
  const viewport = window.visualViewport
  if (!visible || !viewport) return
  const updateViewport = () => {
    editorViewportStyle.value = {
      '--investment-editor-height': `${viewport.height}px`,
      '--investment-editor-top': `${viewport.offsetTop}px`,
    }
  }
  updateViewport()
  viewport.addEventListener('resize', updateViewport)
  viewport.addEventListener('scroll', updateViewport)
  onCleanup(() => {
    viewport.removeEventListener('resize', updateViewport)
    viewport.removeEventListener('scroll', updateViewport)
  })
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
  const lookupSymbol = investmentItemLookupSymbol(item)
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

function initCharts() {
  if (vxnChartEl.value && !vxnChart) {
    vxnChart = echarts.init(vxnChartEl.value)
  }
  if (fearGreedChartEl.value && !fearGreedChart) {
    fearGreedChart = echarts.init(fearGreedChartEl.value)
  }
  if (allocationChartEl.value && !allocationChart) {
    allocationChart = echarts.init(allocationChartEl.value)
  }
}

function renderSentimentCharts() {
  initCharts()
  const colors = chartThemeColors()
  renderMarketChart(vxnChart, vxnSeries.value, colors.violet, {
    min: undefined,
    max: undefined,
    markLines: [
      { yAxis: 22, name: 'Low' },
      { yAxis: 30, name: 'High' },
    ],
  })
  renderMarketChart(fearGreedChart, fearGreedSeries.value, colors.orange, { min: 0, max: 100 })
}

function renderMarketChart(
  chart: ECharts | null,
  series: MarketSentimentSeries | null,
  color: string,
  options: { min?: number; max?: number; markLines?: Array<{ yAxis: number; name: string }> } = {},
) {
  if (!chart || !series?.points.length) return
  const points = series.points
  const colors = chartThemeColors()
  const chartOption: EChartsOption = {
    animationDuration: 450,
    grid: { left: 36, right: 16, top: 16, bottom: 26 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: colors.surface,
      borderColor: colors.line,
      textStyle: { color: colors.ink },
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
      axisLine: { lineStyle: { color: colors.line } },
      axisLabel: {
        color: colors.text,
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
      axisLabel: { color: colors.text },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: colors.line } },
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
              label: { color: colors.text, formatter: '{b}' },
              lineStyle: { type: 'dashed', color: colors.text, width: 1 },
              data: options.markLines,
            }
          : undefined,
      },
    ],
  }
  chart.setOption(chartOption, true)
}

function renderAllocationChart() {
  initCharts()
  if (!allocationChart) return
  if (!allocationEntries.value.length) {
    allocationChart.clear()
    return
  }
  const colors = chartThemeColors()
  const positivePalette = isDark.value
    ? ['#176747', '#1a7653', '#1d815b', '#226c50', '#1b5f47']
    : ['#21835d', '#287957', '#1f704f', '#338765', '#247657']
  const negativePalette = isDark.value
    ? ['#823f45', '#93464d', '#743a40']
    : ['#b94b4b', '#a94747', '#c05a5a']
  const neutralPalette = isDark.value
    ? ['#31566c', '#3d5c70', '#345267']
    : ['#3f7898', '#4d829d', '#47748e']
  const data = allocationEntries.value.map((entry, index) => {
    const palette = entry.type.toLowerCase() === 'cash'
      ? neutralPalette
      : entry.profitPercent < 0
        ? negativePalette
        : positivePalette
    return {
      name: entry.label,
      value: entry.value,
      share: entry.share,
      profit: entry.profit,
      profitPercent: entry.profitPercent,
      type: entry.type,
      count: entry.count,
      itemStyle: { color: palette[index % palette.length] },
    }
  })
  const chartOption: EChartsOption = {
    animationDuration: 420,
    tooltip: {
      confine: true,
      backgroundColor: colors.surface,
      borderColor: colors.line,
      textStyle: { color: colors.ink },
      formatter: (params) => {
        const datum = (params as { data?: (typeof data)[number] }).data
        if (!datum) return ''
        const returnLabel = datum.type.toLowerCase() === 'cash' ? 'Cash position' : formatPercent(datum.profitPercent)
        return [
          `<strong>${escapeHtml(datum.name)}</strong>${datum.count > 1 ? ` · ${datum.count} positions` : ''}`,
          `${formatMoney(datum.value, displayCurrency.value)} · ${formatAllocation(datum.share)}`,
          returnLabel,
        ].join('<br/>')
      },
    },
    series: [
      {
        type: 'treemap',
        data,
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        squareRatio: 1.15,
        visibleMin: 160,
        label: {
          show: true,
          color: '#ffffff',
          fontWeight: 800,
          fontSize: 12,
          lineHeight: 18,
          overflow: 'truncate',
          formatter: (params) => {
            const datum = (params as { data?: (typeof data)[number] }).data
            if (!datum) return ''
            const returnLabel = datum.type.toLowerCase() === 'cash' ? 'Cash' : formatPercent(datum.profitPercent)
            return `${datum.name}\n${formatAllocation(datum.share)}\n${returnLabel}`
          },
        },
        itemStyle: {
          borderColor: colors.surface,
          borderWidth: 3,
          gapWidth: 3,
        },
        emphasis: {
          label: { show: true },
          itemStyle: { borderColor: colors.ink, borderWidth: 2 },
        },
      },
    ],
  }
  allocationChart.setOption(chartOption, true)
}

function resizeCharts() {
  vxnChart?.resize()
  fearGreedChart?.resize()
  allocationChart?.resize()
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
  if (!hasProfitTrend(item)) return 0
  return round2(investmentItemProfit(item))
}

function rowProfitInDisplay(item: InvestmentItem) {
  const sourceCurrency = normalizeCurrency(item.currency || portfolio.value.currency || displayCurrency.value)
  return round2(convertMoney(rowProfit(item), sourceCurrency, displayCurrency.value))
}

function rowCurrency(item: InvestmentItem) {
  return normalizeCurrency(item.currency || portfolio.value.currency || displayCurrency.value)
}

function rowValueInDisplay(item: InvestmentItem) {
  return round2(convertMoney(investmentItemAmount(item), rowCurrency(item), displayCurrency.value))
}

function rowAllocation(item: InvestmentItem) {
  if (Math.abs(totalAll.value) <= 1e-9) return 0
  return rowValueInDisplay(item) / totalAll.value
}

function positionSymbol(item: InvestmentItem) {
  return investmentItemLookupSymbol(item) || item.name || '—'
}

function positionName(item: InvestmentItem) {
  const symbol = positionSymbol(item)
  if (item.name && item.name.trim().toUpperCase() !== symbol.toUpperCase()) return item.name
  return [item.type, item.account].filter(Boolean).join(' · ') || 'Investment position'
}

function positionMonogram(item: InvestmentItem) {
  const value = positionSymbol(item).replace(/[^A-Z0-9]/gi, '')
  return (value.slice(0, 2) || '•').toUpperCase()
}

function rowProfitPercent(item: InvestmentItem) {
  const cost = investmentItemCost(item)
  if (Math.abs(cost) <= 1e-9) return 0
  return (rowProfit(item) / cost) * 100
}

function rowProfitClass(item: InvestmentItem) {
  if (!hasProfitTrend(item)) return ''
  return rowProfitInDisplay(item) >= 0 ? 'positive' : 'negative'
}

function hasProfitTrend(item: InvestmentItem) {
  return String(item.type || '').trim().toLowerCase() !== 'cash'
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

function escapeHtml(value: string) {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  })[character] || character)
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

    <section class="panel allocation-panel" style="margin-top: 14px">
      <div class="section-head">
        <div>
          <h2>Allocation</h2>
          <span class="section-subtitle">Tile size shows portfolio weight. Color shows total return; cash is blue.</span>
        </div>
        <div class="allocation-total">
          <span>Total</span>
          <strong>{{ formatMoney(totalAll, displayCurrency) }}</strong>
        </div>
      </div>
      <div class="allocation-chart-wrap">
        <div ref="allocationChartEl" class="allocation-treemap" role="img" aria-label="Portfolio allocation treemap"></div>
        <div v-if="!allocationEntries.length" class="allocation-empty">
          <strong>No allocation yet</strong>
          <span>Add positions with a market value to build the treemap.</span>
        </div>
      </div>
    </section>

    <section class="panel positions-panel" style="margin-top: 14px">
      <div class="section-head positions-head">
        <div>
          <h2>{{ sortedHoldingItems.length }} Positions</h2>
          <span class="section-subtitle">
            Total return
            <b :class="{ positive: totalProfitPercent >= 0, negative: totalProfitPercent < 0 }">{{ formatPercent(totalProfitPercent) }}</b>
            · Select a position to edit
          </span>
        </div>
        <el-button type="primary" plain :icon="Plus" @click="addItem">Add Holding</el-button>
      </div>

      <div v-if="sortedHoldingItems.length" class="positions-grid">
        <button
          v-for="(item, index) in sortedHoldingItems"
          :key="item.id"
          type="button"
          class="position-card"
          :aria-label="`Edit ${positionSymbol(item)}`"
          @click="openEditor(item)"
        >
          <span class="position-rank">#{{ index + 1 }}</span>
          <span class="position-mark" :class="`tone-${index % 6}`">{{ positionMonogram(item) }}</span>
          <span class="position-identity">
            <strong>{{ positionSymbol(item) }}</strong>
            <small>{{ positionName(item) }}</small>
            <small>{{ formatAllocation(rowAllocation(item)) }} · {{ item.category || 'Available' }}</small>
          </span>
          <span class="position-values">
            <strong>{{ formatMoney(rowValueInDisplay(item), displayCurrency) }}</strong>
            <small v-if="hasProfitTrend(item)" :class="rowProfitClass(item)">
              {{ formatMoney(rowProfitInDisplay(item), displayCurrency) }} ({{ formatPercent(rowProfitPercent(item)) }})
            </small>
            <small v-else class="position-cash-label">Cash position</small>
          </span>
        </button>
      </div>
      <div v-else class="positions-empty">
        <strong>No positions yet</strong>
        <span>Add a holding to build your portfolio view.</span>
      </div>
    </section>

    <el-dialog
      v-model="showEditor"
      class="snapshot-dialog investment-editor-dialog"
      :style="editorViewportStyle"
      width="min(720px, calc(100% - 32px))"
      top="5vh"
      append-to-body
      :close-on-click-modal="false"
      destroy-on-close
      @close="onEditorClose"
      @closed="onEditorClosed"
    >
      <template #header="{ titleId }">
        <div class="dialog-title">
          <div>
            <span>Investment Editor</span>
            <strong :id="titleId">{{ isCreatingItem ? 'New Holding' : 'Edit Holding' }}</strong>
          </div>
          <div class="dialog-summary" v-if="editorDraft">
            <span>Market {{ formatMoney(investmentItemAmount(editorDraft), editorDraft.currency || portfolio.currency) }}</span>
            <span v-if="hasProfitTrend(editorDraft)" :class="rowProfitClass(editorDraft)">P/L {{ formatMoney(rowProfitInDisplay(editorDraft), displayCurrency) }}</span>
          </div>
        </div>
      </template>

      <template v-if="editorDraft">
        <div class="investment-editor-fields">
          <label class="investment-editor-wide">
            <span>Asset</span>
            <el-input v-model="editorDraft.name" aria-label="Asset" placeholder="AAPL, BTC, Cash, SPY..." />
          </label>
          <label>
            <span>Type</span>
            <el-select v-model="editorDraft.type" aria-label="Type" filterable allow-create default-first-option>
              <el-option v-for="itemType in investmentTypeOptions" :key="itemType" :label="itemType" :value="itemType" />
            </el-select>
          </label>
          <label>
            <span>Currency</span>
            <el-select v-model="editorDraft.currency" aria-label="Currency">
              <el-option v-for="currency in currencyOptions" :key="currency" :label="currency" :value="currency" />
            </el-select>
          </label>
          <label>
            <span>Category</span>
            <el-select v-model="editorDraft.category" aria-label="Category" filterable allow-create default-first-option>
              <el-option v-for="category in investmentCategoryOptions" :key="category" :label="category" :value="category" />
            </el-select>
          </label>
          <label v-if="isShareBasedType(editorDraft.type)">
            <span>Symbol</span>
            <el-input v-model="editorDraft.symbol" aria-label="Symbol" placeholder="AAPL / FBTC.CA" autocapitalize="characters" :spellcheck="false" @blur="refreshEditorQuote" />
          </label>
          <label v-if="isShareBasedType(editorDraft.type)">
            <span>Shares</span>
            <el-input-number v-model="editorDraft.shares" aria-label="Shares" inputmode="decimal" :precision="2" :controls="false" />
          </label>
          <label v-if="isShareBasedType(editorDraft.type)">
            <span>Cost / Unit</span>
            <el-input-number v-model="editorDraft.costBasis" aria-label="Cost / Unit" inputmode="decimal" :precision="2" :controls="false" />
          </label>
          <label v-if="isShareBasedType(editorDraft.type)" class="investment-editor-wide">
            <span>Market / Unit</span>
            <el-input :model-value="formatNumber(editorDraft.unitPrice)" aria-label="Market / Unit" readonly />
          </label>
          <label v-else>
            <span>Amount</span>
            <el-input-number v-model="editorDraft.amount" aria-label="Amount" inputmode="decimal" :precision="2" :controls="false" />
          </label>
          <label class="investment-editor-wide">
            <span>Notes</span>
            <el-input v-model="editorDraft.notes" aria-label="Notes" type="textarea" :rows="2" resize="vertical" />
          </label>
        </div>
      </template>

      <template #footer>
        <div class="investment-editor-actions">
          <el-button v-if="!isCreatingItem" :icon="Delete" type="danger" plain @click="deleteFromEditor">Delete</el-button>
          <el-button type="primary" @click="closeEditor">Done</el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>
