import { sampleHoldings, type Holding } from './portfolio'
import { sampleFinanceState, type FinanceState } from './finance'

const holdingsStorageKey = 'fire.holdings.v1'
const financeStorageKey = 'fire.finance.v1'

export function loadHoldings(): Holding[] {
  const raw = localStorage.getItem(holdingsStorageKey)
  if (!raw) return cloneHoldings(sampleHoldings)

  try {
    const parsed = JSON.parse(raw) as Holding[]
    return Array.isArray(parsed) ? parsed : cloneHoldings(sampleHoldings)
  } catch {
    return cloneHoldings(sampleHoldings)
  }
}

export function saveHoldings(holdings: Holding[]) {
  localStorage.setItem(holdingsStorageKey, JSON.stringify(holdings))
}

export function resetHoldings() {
  localStorage.removeItem(holdingsStorageKey)
  return cloneHoldings(sampleHoldings)
}

function cloneHoldings(holdings: Holding[]) {
  return holdings.map((holding) => ({ ...holding }))
}

export function loadFinanceState(): FinanceState {
  const raw = localStorage.getItem(financeStorageKey)
  if (!raw) return cloneFinanceState(sampleFinanceState)

  try {
    const parsed = JSON.parse(raw) as FinanceState
    if (!Array.isArray(parsed.months) || !Array.isArray(parsed.ledger) || !Array.isArray(parsed.forecast)) {
      return cloneFinanceState(sampleFinanceState)
    }
    return parsed
  } catch {
    return cloneFinanceState(sampleFinanceState)
  }
}

export function saveFinanceState(state: FinanceState) {
  localStorage.setItem(financeStorageKey, JSON.stringify(state))
}

export function resetFinanceState() {
  localStorage.removeItem(financeStorageKey)
  return cloneFinanceState(sampleFinanceState)
}

function cloneFinanceState(state: FinanceState): FinanceState {
  return JSON.parse(JSON.stringify(state)) as FinanceState
}
