export interface InvestmentItem {
  id: string
  name: string
  account: string
  category: string
  amount: number
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

export function createInvestmentItem(item?: Partial<InvestmentItem>): InvestmentItem {
  return {
    id: crypto.randomUUID(),
    name: item?.name ?? '',
    account: item?.account ?? '',
    category: item?.category ?? '',
    amount: item?.amount ?? 0,
    notes: item?.notes ?? '',
  }
}

export function createSnapshotFromPrevious(previous?: InvestmentSnapshot): InvestmentSnapshot {
  return {
    id: crypto.randomUUID(),
    date: new Date().toISOString().slice(0, 10),
    currency: previous?.currency ?? 'CAD',
    notes: '',
    items: previous?.items.length ? previous.items.map((item) => createInvestmentItem(item)) : [createInvestmentItem()],
  }
}

export function snapshotTotal(snapshot?: InvestmentSnapshot) {
  if (!snapshot) return 0
  return roundMoney(snapshot.items.reduce((sum, item) => sum + item.amount, 0))
}

export function sortedSnapshots(state: InvestmentState) {
  return [...state.snapshots].sort((a, b) => b.date.localeCompare(a.date))
}

export function trendPoints(state: InvestmentState) {
  return [...state.snapshots]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((snapshot) => ({
      id: snapshot.id,
      date: snapshot.date,
      currency: snapshot.currency,
      total: snapshotTotal(snapshot),
    }))
}

function roundMoney(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 100) / 100
}
