import { convertMoney, normalizeCurrency, type CurrencyCode } from './currency'

export const investmentCategoryOptions = [
  'Available',
  'Locked',
] as const

export const investmentTypeOptions = [
  'Cash',
  'Stock',
  'ETF',
  'Option',
  'Bond',
  'Crypto',
  'Fund',
  'Other',
] as const

export interface InvestmentItem {
  id: string
  name: string
  symbol?: string
  account: string
  type: string
  category: string
  shares?: number
  unitPrice?: number
  costBasis?: number
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

export type InvestmentCategoryFilter = 'available' | 'locked' | 'liability' | 'all'

const CANADIAN_LISTING_SUFFIXES = new Set(['CA', 'TO', 'TSX'])
const UNDERLYING_SYMBOL_ALIASES: Record<string, string> = {
  GOOG: 'GOOGL',
}

export const emptyInvestmentState = (): InvestmentState => ({
  snapshots: [],
})

export function createInvestmentItem(item?: Partial<InvestmentItem>, defaultCurrency = 'CAD'): InvestmentItem {
  const type = normalizeInvestmentType(item?.type, 'Cash')
  const shares = Number.isFinite(item?.shares) ? Number(item?.shares) : 0
  const unitPrice = Number.isFinite(item?.unitPrice) ? Number(item?.unitPrice) : 0
  const category = normalizeInvestmentCategory(item?.category)
  const rawAmount = Number.isFinite(item?.amount) ? Number(item?.amount) : 0
  const amount = normalizeInvestmentAmount(category, rawAmount)
  const isShareBased = isShareBasedType(type)
  const multiplier = investmentContractMultiplier(type)
  const defaultCostBasis = isShareBased
    ? (unitPrice || (shares ? amount / (shares * multiplier) : 0))
    : amount
  const inputCostBasis = Number.isFinite(item?.costBasis) ? Number(item?.costBasis) : NaN
  const normalizedCostBasis = Number.isFinite(inputCostBasis) && Math.abs(inputCostBasis) > 1e-9 ? inputCostBasis : defaultCostBasis
  return {
    id: crypto.randomUUID(),
    name: item?.name ?? '',
    symbol: item?.symbol ?? '',
    account: item?.account ?? '',
    type,
    category,
    shares,
    unitPrice,
    costBasis: normalizedCostBasis,
    amount,
    currency: item?.currency ?? defaultCurrency,
    notes: item?.notes ?? '',
  }
}

export function normalizeInvestmentCategory(category?: string) {
  if (!category) return 'Available'
  if (category === 'Liability' || category === 'Debt' || category === 'Debit' || category === 'Credit Card') return 'Liability'
  if (category === 'Locked' || category === 'Retirement' || category === 'Housing Fund' || category === 'Insurance' || category === 'Deposit') return 'Locked'
  return 'Available'
}

export function normalizeInvestmentAmount(category?: string, amount?: number) {
  const value = Number(amount)
  const normalizedAmount = Number.isFinite(value) ? Math.abs(value) : 0
  return normalizeInvestmentCategory(category) === 'Liability' ? -normalizedAmount : normalizedAmount
}

export function normalizeInvestmentType(type?: string, fallback = 'Other') {
  if (!type) return fallback
  const value = String(type).trim().toLowerCase()
  if (value === 'cash') return 'Cash'
  if (value === 'credit card' || value === 'credit-card' || value === 'card') return 'Credit Card'
  if (value === 'loan' || value === 'debt' || value === 'liability') return 'Loan'
  if (value === 'stock') return 'Stock'
  if (value === 'etf') return 'ETF'
  if (value === 'option') return 'Option'
  if (value === 'bond') return 'Bond'
  if (value === 'crypto') return 'Crypto'
  if (value === 'fund') return 'Fund'
  if (value === 'other') return 'Other'
  return String(type).trim() || fallback
}

export function isShareBasedType(type?: string) {
  const normalizedType = normalizeInvestmentType(type, 'Other')
  return normalizedType === 'Stock' || normalizedType === 'ETF' || normalizedType === 'Option' || normalizedType === 'Crypto' || normalizedType === 'Bond' || normalizedType === 'Fund'
}

export function investmentContractMultiplier(type?: string) {
  const normalizedType = normalizeInvestmentType(type, 'Other')
  if (normalizedType === 'Option') return 100
  return 1
}

export function investmentItemAmount(item: InvestmentItem) {
  if (!isShareBasedType(item.type)) return Number.isFinite(item.amount) ? item.amount : 0
  const shares = Number.isFinite(item.shares) ? Number(item.shares) : 0
  const unitPrice = Number.isFinite(item.unitPrice) ? Number(item.unitPrice) : 0
  const computed = shares * unitPrice * investmentContractMultiplier(item.type)
  if (Math.abs(computed) > 1e-9) return computed
  return Number.isFinite(item.amount) ? item.amount : 0
}

export function investmentItemCost(item: InvestmentItem) {
  if (!isShareBasedType(item.type)) {
    if (Number.isFinite(item.costBasis) && Math.abs(Number(item.costBasis)) > 1e-9) return Number(item.costBasis)
    return Number.isFinite(item.amount) ? Number(item.amount) : 0
  }
  const shares = Number.isFinite(item.shares) ? Number(item.shares) : 0
  const costBasis = Number.isFinite(item.costBasis) ? Number(item.costBasis) : 0
  const computed = shares * costBasis * investmentContractMultiplier(item.type)
  if (Math.abs(computed) > 1e-9) return computed
  if (Number.isFinite(item.amount) && Math.abs(Number(item.amount)) > 1e-9) return Number(item.amount)
  return investmentItemAmount(item)
}

export function investmentItemProfit(item: InvestmentItem) {
  return investmentItemAmount(item) - investmentItemCost(item)
}

export function normalizeInvestmentLookupSymbol(value?: string) {
  const normalized = String(value || '').trim().toUpperCase().replace(/\s+/g, '')
  if (!normalized) return ''
  const parts = normalized.split('-').filter(Boolean)
  if (parts.length >= 3) {
    return parts[parts.length - 1] ?? ''
  }
  return normalized
}

export function investmentItemLookupSymbol(item: InvestmentItem) {
  return normalizeInvestmentLookupSymbol(item.symbol || item.name)
}

export function investmentItemMergeSymbol(item: InvestmentItem) {
  const lookupSymbol = investmentItemLookupSymbol(item)
  if (!lookupSymbol) return ''
  const [base, suffix] = lookupSymbol.split('.')
  const symbolBase = suffix && base && CANADIAN_LISTING_SUFFIXES.has(suffix) ? base : lookupSymbol
  return UNDERLYING_SYMBOL_ALIASES[symbolBase] || symbolBase
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
  category: InvestmentCategoryFilter,
) {
  if (!snapshot) return 0
  return roundMoney(
    snapshot.items.reduce((sum, item) => {
      const normalizedCategory = normalizeInvestmentCategory(item.category)
      if (category === 'available' && normalizedCategory !== 'Available') return sum
      if (category === 'locked' && normalizedCategory !== 'Locked') return sum
      if (category === 'liability' && normalizedCategory !== 'Liability') return sum
      const itemCurrency = normalizeCurrency(item.currency || snapshot.currency || targetCurrency)
      const amount = normalizedCategory === 'Liability'
        ? normalizeInvestmentAmount(normalizedCategory, investmentItemAmount(item))
        : investmentItemAmount(item)
      return sum + convertMoney(amount, itemCurrency, targetCurrency)
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
  category: InvestmentCategoryFilter,
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
