import type { FinanceState } from './finance'

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
