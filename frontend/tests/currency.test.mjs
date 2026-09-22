import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createServer } from 'vite'
import { computed } from 'vue'

const storage = new Map()
globalThis.localStorage = {getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value)}
const server = await createServer({server: {middlewareMode: true}, appType: 'custom'})
const fx = await server.ssrLoadModule('/src/lib/currency.ts')
const finance = await server.ssrLoadModule('/src/lib/finance.ts')
const state = {
  base: 'CAD', rates: {CAD: 1, CNY: 0.2094, USD: 1.4021, EUR: 1.6086},
  date: '2026-09-21', fetchedAt: new Date().toISOString(), source: 'Bank of Canada', stale: false,
}
const near = (actual, expected) => assert(Math.abs(actual - expected) < 0.000001, `${actual} != ${expected}`)

try {
  await test('No hardcoded conversion is used before rates load', () => {
    assert.equal(fx.exchangeRates.value, null)
    assert(Number.isNaN(fx.convertMoney(100, 'CAD', 'CNY')))
    assert.equal(fx.formatMoney(100, 'CAD'), '—')
    assert.equal(fx.convertMoney(100, 'CAD', 'CAD'), 100)
  })
  await test('Concurrent refreshes share one request and persist validated rates', async () => {
    let calls = 0
    globalThis.fetch = async () => { calls++; return {ok: true, json: async () => state} }
    await Promise.all([fx.refreshExchangeRates(true), fx.refreshExchangeRates(true)])
    assert.equal(calls, 1)
    assert.equal(JSON.parse(storage.get('fire.exchangeRates.v1')).rates.CNY, 0.2094)
  })
  await test('CAD/CNY inversion, USD/EUR cross rates, and round trips', () => {
    near(fx.convertMoney(1000, 'CAD', 'CNY'), 1000 / 0.2094)
    near(fx.convertMoney(1000, 'CNY', 'CAD'), 209.4)
    near(fx.convertMoney(1000, 'USD', 'EUR'), 1000 * 1.4021 / 1.6086)
    near(fx.convertMoney(fx.convertMoney(-1234.56, 'CAD', 'CNY'), 'CNY', 'CAD'), -1234.56)
  })
  await test('Financial summaries and ledger use the same rates, including EUR', () => {
    const item = (amount, currency) => ({id: currency, name: currency, amount, currency, notes: ''})
    const month = {...finance.emptyMonth(), currency: 'CAD', income: [item(100, 'USD'), item(100, 'EUR'), item(100, 'CNY')], expenses: [], assets: [], liabilities: []}
    assert.equal(finance.summarizeMonth(month).totalIncome, 322.01)
    const ledger = [{...item(100, 'EUR'), category: 'Income', date: '2026-09-21'}]
    assert.equal(finance.summarizeLedger(ledger, 'CAD').income, 160.86)
  })
  await test('Totals react when updated rates arrive', async () => {
    const converted = computed(() => fx.convertMoney(100, 'CAD', 'CNY'))
    near(converted.value, 100 / 0.2094)
    globalThis.fetch = async () => ({ok: true, json: async () => ({...state, rates: {...state.rates, CNY: 0.2}})})
    await fx.refreshExchangeRates(true)
    near(converted.value, 500)
  })
  await test('Failed or invalid refreshes keep last good values and disclose cache', async () => {
    for (const response of [{ok: false}, {ok: true, json: async () => ({...state, rates: {...state.rates, CNY: 0}})}]) {
      globalThis.fetch = async () => response
      await fx.refreshExchangeRates(true)
      assert.equal(fx.exchangeRates.value.rates.CNY, 0.2)
      assert.equal(fx.exchangeRates.value.stale, true)
      assert.match(fx.exchangeRatesNotice.value, /cached rates/)
    }
  })
  await test('Successful refresh clears warning even if browser storage is disabled', async () => {
    globalThis.localStorage.setItem = () => {throw new Error('disabled')}
    globalThis.fetch = async () => ({ok: true, json: async () => state})
    await fx.refreshExchangeRates(true)
    assert.equal(fx.exchangeRates.value.stale, false)
    assert.equal(fx.exchangeRatesNotice.value, '')
  })
} finally {
  await server.close()
}
