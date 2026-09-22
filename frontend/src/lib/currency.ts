import { computed, ref, watch } from 'vue'

export type CurrencyCode = 'CNY' | 'CAD' | 'USD' | 'EUR'
export interface ExchangeRates {
  base: 'CAD'
  rates: Record<CurrencyCode, number>
  date: string
  fetchedAt: string
  source: string
  stale: boolean
}

const storageKey = 'fire.displayCurrency'
const ratesStorageKey = 'fire.exchangeRates.v1'
const apiBase = import.meta.env.VITE_API_BASE ?? ''
export const currencyOptions: CurrencyCode[] = ['CNY', 'CAD', 'USD', 'EUR']

function readStorage(key: string) {
  try { return localStorage.getItem(key) } catch { return null }
}

function validRates(value: unknown): value is ExchangeRates {
  if (!value || typeof value !== 'object') return false
  const state = value as ExchangeRates
  return state.base === 'CAD' && state.source === 'Bank of Canada'
    && typeof state.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(state.date)
    && Number.isFinite(Date.parse(state.date)) && Number.isFinite(Date.parse(state.fetchedAt))
    && state.rates?.CAD === 1
    && currencyOptions.every((code) => Number.isFinite(state.rates[code]) && state.rates[code] > 0)
    && typeof state.stale === 'boolean'
}

function loadCachedRates(): ExchangeRates | null {
  try {
    const state: unknown = JSON.parse(readStorage(ratesStorageKey) || 'null')
    return validRates(state) ? { ...state, stale: true } : null
  } catch { return null }
}

const savedCurrency = readStorage(storageKey)
export const displayCurrency = ref<CurrencyCode>(
  currencyOptions.includes(savedCurrency as CurrencyCode) ? savedCurrency as CurrencyCode : 'CNY',
)
export const exchangeRates = ref<ExchangeRates | null>(loadCachedRates())
export const exchangeRatesLoading = ref(false)
export const exchangeRatesError = ref('')
let pendingRefresh: Promise<void> | null = null
let lastAttemptAt = 0

export const currencyHint = computed(() => {
  const label = `Display converted to ${displayCurrency.value}`
  return exchangeRates.value ? `${label} · 1 CAD = ${convertMoney(1, 'CAD', 'CNY').toFixed(4)} CNY` : label
})

export const exchangeRatesNotice = computed(() => {
  if (exchangeRatesError.value) return exchangeRatesError.value
  if (exchangeRates.value?.stale) return `Using cached exchange rates from ${exchangeRates.value.date}; latest rates could not be confirmed.`
  return ''
})

watch(displayCurrency, (nextCurrency) => {
  try { localStorage.setItem(storageKey, nextCurrency) } catch { /* Storage may be disabled. */ }
})

export function refreshExchangeRates(force = false): Promise<void> {
  if (pendingRefresh) return pendingRefresh
  if (!force && Date.now() - lastAttemptAt < 60 * 60 * 1000) return Promise.resolve()
  lastAttemptAt = Date.now()
  exchangeRatesLoading.value = true
  pendingRefresh = (async () => {
    try {
      const response = await fetch(`${apiBase}/api/exchange-rates`, { signal: AbortSignal.timeout(12000) })
      if (!response.ok) throw new Error('Exchange rates request failed')
      const state: unknown = await response.json()
      if (!validRates(state)) throw new Error('Invalid exchange rates')
      exchangeRates.value = state
      exchangeRatesError.value = ''
      try { localStorage.setItem(ratesStorageKey, JSON.stringify(state)) } catch { /* Keep in-memory rates. */ }
    } catch {
      if (exchangeRates.value) {
        exchangeRates.value = { ...exchangeRates.value, stale: true }
        exchangeRatesError.value = `Could not update exchange rates. Using cached rates from ${exchangeRates.value.date}.`
      } else {
        exchangeRatesError.value = 'Exchange rates are unavailable. Retry to load converted totals.'
      }
      // Retry sooner after a failed request when the app returns to the foreground.
      lastAttemptAt = Date.now() - 60 * 60 * 1000 + 60 * 1000
    } finally {
      exchangeRatesLoading.value = false
      pendingRefresh = null
    }
  })()
  return pendingRefresh
}

export function setDisplayCurrency(currency: CurrencyCode) {
  displayCurrency.value = currency
}

export function formatMoney(value: number, sourceCurrency: string = displayCurrency.value) {
  const target = displayCurrency.value
  const converted = convertMoney(value, normalizeCurrency(sourceCurrency), target)
  if (!Number.isFinite(converted)) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: target }).format(converted)
}

export function convertMoney(value: number, sourceCurrency: CurrencyCode, targetCurrency: CurrencyCode) {
  if (sourceCurrency === targetCurrency || value === 0) return value
  const rates = exchangeRates.value?.rates
  if (!rates) return Number.NaN
  return value * rates[sourceCurrency] / rates[targetCurrency]
}

export function normalizeCurrency(currency: string): CurrencyCode {
  if (currencyOptions.includes(currency as CurrencyCode)) return currency as CurrencyCode
  return displayCurrency.value
}
