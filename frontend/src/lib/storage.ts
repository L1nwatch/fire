import { sampleHoldings, type Holding } from './portfolio'

const holdingsStorageKey = 'fire.holdings.v1'

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
