import { convertMoney, normalizeCurrency, type CurrencyCode } from './currency'

export const investmentCategoryOptions = [
  'Available',
  'Locked',
] as const

export interface InvestmentItem {
  id: string
  name: string
  account: string
  category: string
  amount: number
  currency?: string
  notes: string
}

export interface InvestmentSnapshot {
  id: string
  date: string
  currency: string
  notes: string
  items: InvestmentItem[]
}

export interface InvestmentState {
  snapshots: InvestmentSnapshot[]
}

export const emptyInvestmentState = (): InvestmentState => ({
  snapshots: [],
})

export function createInvestmentItem(item?: Partial<InvestmentItem>, defaultCurrency = 'CAD'): InvestmentItem {
  return {
    id: crypto.randomUUID(),
    name: item?.name ?? '',
    account: item?.account ?? '',
    category: normalizeInvestmentCategory(item?.category),
    amount: item?.amount ?? 0,
    currency: item?.currency ?? defaultCurrency,
    notes: item?.notes ?? '',
  }
}

export function normalizeInvestmentCategory(category?: string) {
  if (!category) return 'Available'
  if (category === 'Locked' || category === 'Retirement' || category === 'Housing Fund' || category === 'Insurance' || category === 'Deposit') return 'Locked'
  return 'Available'
}

export function createSnapshotFromPrevious(previous?: InvestmentSnapshot): InvestmentSnapshot {
  return {
    id: crypto.randomUUID(),
    date: new Date().toISOString().slice(0, 10),
    currency: previous?.currency ?? 'CAD',
    notes: '',
    items: previous?.items.length
      ? previous.items.map((item) => createInvestmentItem(item, previous.currency))
      : [createInvestmentItem(undefined, previous?.currency ?? 'CAD')],
  }
}

export function snapshotTotal(snapshot: InvestmentSnapshot | undefined, targetCurrency: CurrencyCode) {
  return snapshotTotalByCategory(snapshot, targetCurrency, 'all')
}

export function snapshotTotalByCategory(
  snapshot: InvestmentSnapshot | undefined,
  targetCurrency: CurrencyCode,
  category: 'available' | 'locked' | 'all',
) {
  if (!snapshot) return 0
  return roundMoney(
    snapshot.items.reduce((sum, item) => {
      const normalizedCategory = normalizeInvestmentCategory(item.category)
      if (category === 'available' && normalizedCategory !== 'Available') return sum
      if (category === 'locked' && normalizedCategory !== 'Locked') return sum
      const itemCurrency = normalizeCurrency(item.currency || snapshot.currency || targetCurrency)
      return sum + convertMoney(item.amount, itemCurrency, targetCurrency)
    }, 0),
  )
}

export function sortedSnapshots(state: InvestmentState) {
  return [...state.snapshots].sort((a, b) => b.date.localeCompare(a.date))
}

export function trendPoints(state: InvestmentState, targetCurrency: CurrencyCode) {
  return trendPointsByCategory(state, targetCurrency, 'all')
}

export function trendPointsByCategory(
  state: InvestmentState,
  targetCurrency: CurrencyCode,
  category: 'available' | 'locked' | 'all',
) {
  return [...state.snapshots]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((snapshot) => ({
      id: snapshot.id,
      date: snapshot.date,
      currency: targetCurrency,
      total: snapshotTotalByCategory(snapshot, targetCurrency, category),
    }))
}

function roundMoney(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 100) / 100
}
