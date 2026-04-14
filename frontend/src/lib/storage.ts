import { sampleHoldings, type Holding } from './portfolio'

const storageKey = 'fire.holdings.v1'

export function loadHoldings(): Holding[] {
  const raw = localStorage.getItem(storageKey)
  if (!raw) return cloneHoldings(sampleHoldings)

  try {
    const parsed = JSON.parse(raw) as Holding[]
    return Array.isArray(parsed) ? parsed : cloneHoldings(sampleHoldings)
  } catch {
    return cloneHoldings(sampleHoldings)
  }
}

export function saveHoldings(holdings: Holding[]) {
  localStorage.setItem(storageKey, JSON.stringify(holdings))
}

export function resetHoldings() {
  localStorage.removeItem(storageKey)
  return cloneHoldings(sampleHoldings)
}

function cloneHoldings(holdings: Holding[]) {
  return holdings.map((holding) => ({ ...holding }))
}
