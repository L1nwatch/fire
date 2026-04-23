import type { FinanceState } from './finance'
import type { InvestmentState } from './investments'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

export async function fetchFinanceState(): Promise<FinanceState> {
  const response = await fetch(`${apiBase}/api/finance`)
  if (!response.ok) {
    throw new Error(`Failed to load finance data: ${response.status}`)
  }
  return (await response.json()) as FinanceState
}

export async function saveFinanceStateToDb(state: FinanceState): Promise<void> {
  const response = await fetch(`${apiBase}/api/finance`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state),
  })
  if (!response.ok) {
    throw new Error(`Failed to save finance data: ${response.status}`)
  }
}

export async function fetchInvestmentState(): Promise<InvestmentState> {
  const response = await fetch(`${apiBase}/api/investments`)
  if (!response.ok) {
    throw new Error(`Failed to load investments: ${response.status}`)
  }
  return (await response.json()) as InvestmentState
}

export async function saveInvestmentStateToDb(state: InvestmentState): Promise<void> {
  const response = await fetch(`${apiBase}/api/investments`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state),
  })
  if (!response.ok) {
    throw new Error(`Failed to save investments: ${response.status}`)
  }
}

export async function fetchPortfolioState(): Promise<InvestmentState> {
  const response = await fetch(`${apiBase}/api/portfolio`)
  if (!response.ok) {
    throw new Error(`Failed to load portfolio: ${response.status}`)
  }
  return (await response.json()) as InvestmentState
}

export async function savePortfolioStateToDb(state: InvestmentState): Promise<void> {
  const response = await fetch(`${apiBase}/api/portfolio`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state),
  })
  if (!response.ok) {
    throw new Error(`Failed to save portfolio: ${response.status}`)
  }
}

export interface MarketQuote {
  symbol: string
  price: number
  currency: string
  source: string
}

export async function fetchLatestQuote(symbol: string): Promise<MarketQuote> {
  const response = await fetch(`${apiBase}/api/market/quote?symbol=${encodeURIComponent(symbol)}`)
  if (!response.ok) {
    throw new Error(`Failed to load quote for ${symbol}: ${response.status}`)
  }
  return (await response.json()) as MarketQuote
}
