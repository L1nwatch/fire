import { computed, ref, watch } from 'vue'

export type CurrencyCode = 'CNY' | 'CAD' | 'USD'

const storageKey = 'fire.displayCurrency'

const cnyPerUnit: Record<CurrencyCode, number> = {
  CNY: 1,
  CAD: 5.25,
  USD: 7.2,
}

const savedCurrency = localStorage.getItem(storageKey)
export const displayCurrency = ref<CurrencyCode>(savedCurrency === 'CAD' || savedCurrency === 'USD' || savedCurrency === 'CNY' ? savedCurrency : 'CNY')

export const currencyOptions: CurrencyCode[] = ['CNY', 'CAD', 'USD']

export const currencyHint = computed(() => {
  if (displayCurrency.value === 'CAD') return 'Display converted to CAD'
  return 'Display converted to CNY'
})

watch(displayCurrency, (nextCurrency) => {
  localStorage.setItem(storageKey, nextCurrency)
})

export function setDisplayCurrency(currency: CurrencyCode) {
  displayCurrency.value = currency
}

export function formatMoney(value: number, sourceCurrency: string = displayCurrency.value) {
  const target = displayCurrency.value
  const converted = convertMoney(value, normalizeCurrency(sourceCurrency), target)
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: target }).format(converted)
}

export function convertMoney(value: number, sourceCurrency: CurrencyCode, targetCurrency: CurrencyCode) {
  if (sourceCurrency === targetCurrency) return value
  const valueInCny = value * cnyPerUnit[sourceCurrency]
  return valueInCny / cnyPerUnit[targetCurrency]
}

export function normalizeCurrency(currency: string): CurrencyCode {
  if (currency === 'CAD' || currency === 'USD' || currency === 'CNY') return currency
  return displayCurrency.value
}
