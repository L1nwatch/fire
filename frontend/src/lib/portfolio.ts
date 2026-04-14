export type AssetClass = 'Equity' | 'ETF' | 'Crypto' | 'Bond' | 'Cash' | 'Alternative'
export type RiskLevel = 'Low' | 'Medium' | 'High'

export interface Holding {
  id: string
  symbol: string
  name: string
  assetClass: AssetClass
  account: string
  quantity: number
  averageCost: number
  marketPrice: number
  targetWeight: number
  risk: RiskLevel
  notes: string
}

export interface PortfolioSummary {
  marketValue: number
  costBasis: number
  gainLoss: number
  gainLossPercent: number
  cashBalance: number
  investedValue: number
}

export interface AllocationRow {
  label: string
  value: number
  weight: number
  targetWeight: number
  drift: number
}

export const assetClasses: AssetClass[] = ['Equity', 'ETF', 'Crypto', 'Bond', 'Cash', 'Alternative']
export const riskLevels: RiskLevel[] = ['Low', 'Medium', 'High']

export const sampleHoldings: Holding[] = [
  {
    id: 'h-1',
    symbol: 'VTI',
    name: 'Total US Market',
    assetClass: 'ETF',
    account: 'Brokerage',
    quantity: 42,
    averageCost: 212.4,
    marketPrice: 254.18,
    targetWeight: 32,
    risk: 'Medium',
    notes: 'Core US equity sleeve',
  },
  {
    id: 'h-2',
    symbol: 'VXUS',
    name: 'Total International Market',
    assetClass: 'ETF',
    account: 'Brokerage',
    quantity: 31,
    averageCost: 55.2,
    marketPrice: 62.7,
    targetWeight: 18,
    risk: 'Medium',
    notes: 'International diversification',
  },
  {
    id: 'h-3',
    symbol: 'BND',
    name: 'Total Bond Market',
    assetClass: 'Bond',
    account: 'IRA',
    quantity: 24,
    averageCost: 72.1,
    marketPrice: 71.35,
    targetWeight: 20,
    risk: 'Low',
    notes: 'Stability reserve',
  },
  {
    id: 'h-4',
    symbol: 'BTC',
    name: 'Bitcoin',
    assetClass: 'Crypto',
    account: 'Cold Wallet',
    quantity: 0.32,
    averageCost: 42100,
    marketPrice: 68450,
    targetWeight: 8,
    risk: 'High',
    notes: 'Volatile long-duration position',
  },
  {
    id: 'h-5',
    symbol: 'CASH',
    name: 'Sweep Cash',
    assetClass: 'Cash',
    account: 'Brokerage',
    quantity: 1,
    averageCost: 4200,
    marketPrice: 4200,
    targetWeight: 12,
    risk: 'Low',
    notes: 'Dry powder and emergency buffer',
  },
]

export function createHolding(): Holding {
  return {
    id: crypto.randomUUID(),
    symbol: '',
    name: '',
    assetClass: 'Equity',
    account: 'Brokerage',
    quantity: 0,
    averageCost: 0,
    marketPrice: 0,
    targetWeight: 0,
    risk: 'Medium',
    notes: '',
  }
}

export function holdingValue(holding: Holding) {
  return roundMoney(holding.quantity * holding.marketPrice)
}

export function holdingCost(holding: Holding) {
  return roundMoney(holding.quantity * holding.averageCost)
}

export function holdingGainLoss(holding: Holding) {
  return roundMoney(holdingValue(holding) - holdingCost(holding))
}

export function holdingGainLossPercent(holding: Holding) {
  const cost = holdingCost(holding)
  if (!cost) return 0
  return roundPercent((holdingGainLoss(holding) / cost) * 100)
}

export function summarizePortfolio(holdings: Holding[]): PortfolioSummary {
  const marketValue = roundMoney(holdings.reduce((sum, holding) => sum + holdingValue(holding), 0))
  const costBasis = roundMoney(holdings.reduce((sum, holding) => sum + holdingCost(holding), 0))
  const gainLoss = roundMoney(marketValue - costBasis)
  const cashBalance = roundMoney(
    holdings.filter((holding) => holding.assetClass === 'Cash').reduce((sum, holding) => sum + holdingValue(holding), 0),
  )
  const investedValue = roundMoney(marketValue - cashBalance)

  return {
    marketValue,
    costBasis,
    gainLoss,
    gainLossPercent: costBasis ? roundPercent((gainLoss / costBasis) * 100) : 0,
    cashBalance,
    investedValue,
  }
}

export function allocationByAssetClass(holdings: Holding[]): AllocationRow[] {
  const total = holdings.reduce((sum, holding) => sum + holdingValue(holding), 0)
  const targets = holdings.reduce<Record<string, number>>((acc, holding) => {
    acc[holding.assetClass] = Math.max(acc[holding.assetClass] ?? 0, holding.targetWeight)
    return acc
  }, {})

  return assetClasses
    .map((assetClass) => {
      const value = holdings
        .filter((holding) => holding.assetClass === assetClass)
        .reduce((sum, holding) => sum + holdingValue(holding), 0)
      const weight = total ? roundPercent((value / total) * 100) : 0
      const targetWeight = targets[assetClass] ?? 0
      return {
        label: assetClass,
        value: roundMoney(value),
        weight,
        targetWeight,
        drift: roundPercent(weight - targetWeight),
      }
    })
    .filter((row) => row.value > 0 || row.targetWeight > 0)
}

function roundMoney(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 100) / 100
}

function roundPercent(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 10) / 10
}
