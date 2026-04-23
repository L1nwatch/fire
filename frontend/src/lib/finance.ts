export type MoneySection = 'income' | 'expense' | 'asset' | 'liability'
export type IncomeCategory = 'Active' | 'Passive'
export const incomeCategoryOptions: IncomeCategory[] = ['Active', 'Passive']

export interface MoneyItem {
  id: string
  name: string
  amount: number
  currency: string
  category?: string
  notes: string
}

export interface FinancialMonth {
  id: string
  label: string
  currency: string
  passiveIncome: number
  conclusion: string
  income: MoneyItem[]
  expenses: MoneyItem[]
  assets: MoneyItem[]
  liabilities: MoneyItem[]
}

export interface DailyLedgerEntry {
  id: string
  date: string
  category: string
  amount: number
  currency: string
  notes: string
}

export const ledgerCategoryOptions = [
  'Income',
  'Expense',
  'Food',
  'Transport',
  'Shopping',
  'Insurance',
  'Telecom',
  'Utilities',
  'Event',
  'Rent',
] as const

export interface ForecastEntry {
  id: string
  event: string
  year: number
  period: string
  months: number
  tuition: number
  rent: number
  utilities: number
  food: number
  phone: number
  other: number
  income: number
  comment: string
}

export interface FinanceState {
  months: FinancialMonth[]
  ledger: DailyLedgerEntry[]
  forecast: ForecastEntry[]
}

export interface FinanceSummary {
  totalIncome: number
  totalExpenses: number
  monthlyCashFlow: number
  totalAssets: number
  totalLiabilities: number
  netWorth: number
  passiveIncome: number
  savingsRate: number
}

type CurrencyCode = 'CNY' | 'CAD' | 'USD'

const cnyPerUnit: Record<CurrencyCode, number> = {
  CNY: 1,
  CAD: 5.25,
  USD: 7.2,
}

export const emptyItem = (name = '', currency = 'CAD', category = ''): MoneyItem => ({
  id: crypto.randomUUID(),
  name,
  amount: 0,
  currency,
  category,
  notes: '',
})

export const emptyMonth = (): FinancialMonth => {
  const currency = 'CAD'
  return {
    id: crypto.randomUUID(),
    label: new Date().toISOString().slice(0, 7),
    currency,
    passiveIncome: 0,
    conclusion: '',
    income: [emptyItem('Salary', currency, 'Active'), emptyItem('Interest', currency, 'Passive')],
    expenses: [
      emptyItem('Food', currency),
      emptyItem('Shopping', currency),
      emptyItem('Transportation', currency),
      emptyItem('Rent', currency),
    ],
    assets: [emptyItem('Cash', currency), emptyItem('Brokerage', currency), emptyItem('Bank account', currency)],
    liabilities: [emptyItem('Credit card', currency), emptyItem('Rent payable', currency)],
  }
}

export const emptyLedgerEntry = (currency = 'CNY'): DailyLedgerEntry => ({
  id: crypto.randomUUID(),
  date: new Date().toISOString().slice(0, 10),
  category: 'Expense',
  amount: 0,
  currency,
  notes: '',
})

export const emptyForecastEntry = (): ForecastEntry => ({
  id: crypto.randomUUID(),
  event: '',
  year: new Date().getFullYear(),
  period: '',
  months: 1,
  tuition: 0,
  rent: 0,
  utilities: 0,
  food: 0,
  phone: 0,
  other: 0,
  income: 0,
  comment: '',
})

export const sampleFinanceState: FinanceState = {
  months: [
    {
      id: 'month-2026-04',
      label: '2026-04',
      currency: 'CAD',
      passiveIncome: 656.92,
      conclusion: 'Recent month from the daily ledger format.',
      income: withCurrency(
        [
          { id: 'income-salary', name: 'Salary / scholarship', amount: 656.92, category: 'Active', notes: '' },
          { id: 'income-interest', name: 'Interest / passive income', amount: 0, category: 'Passive', notes: '' },
        ],
        'CAD',
      ),
      expenses: withCurrency(
        [
          { id: 'expense-food', name: 'Food', amount: -1225.47, notes: '' },
          { id: 'expense-transport', name: 'Transportation', amount: -11402.29, notes: '' },
          { id: 'expense-shopping', name: 'Shopping', amount: -597.66, notes: '' },
          { id: 'expense-rent', name: 'Shipping / rent', amount: -10348.07, notes: '' },
        ],
        'CAD',
      ),
      assets: withCurrency(
        [
          { id: 'asset-cash', name: 'Cash and bank accounts', amount: 4200, notes: '' },
          { id: 'asset-brokerage', name: 'Brokerage / investments', amount: 27180, notes: '' },
        ],
        'CAD',
      ),
      liabilities: withCurrency(
        [
          { id: 'liability-card', name: 'Credit card / bills', amount: -950, notes: '' },
          { id: 'liability-rent', name: 'Rent payable', amount: -10348.07, notes: '' },
        ],
        'CAD',
      ),
    },
    {
      id: 'month-2026-03',
      label: '2026-03',
      currency: 'CAD',
      passiveIncome: 0,
      conclusion: 'Positive cash flow month.',
      income: withCurrency(
        [
          { id: 'income-2026-03-main', name: 'Salary / scholarship', amount: 25086.5, category: 'Active', notes: '' },
          { id: 'income-2026-03-other', name: 'Other income', amount: 0, category: 'Active', notes: '' },
        ],
        'CAD',
      ),
      expenses: withCurrency(
        [
          { id: 'expense-2026-03-food', name: 'Food', amount: -3204.25, notes: '' },
          { id: 'expense-2026-03-shopping', name: 'Shopping', amount: -810.54, notes: '' },
          { id: 'expense-2026-03-rent', name: 'Shipping / rent', amount: -10557.97, notes: '' },
        ],
        'CAD',
      ),
      assets: withCurrency(
        [
          { id: 'asset-2026-03-cash', name: 'Cash and bank accounts', amount: 53800, notes: '' },
          { id: 'asset-2026-03-invest', name: 'Brokerage / investments', amount: 28800, notes: '' },
        ],
        'CAD',
      ),
      liabilities: withCurrency([{ id: 'liability-2026-03-card', name: 'Credit card / bills', amount: -1800, notes: '' }], 'CAD'),
    },
  ],
  ledger: [
    {
      id: 'ledger-1',
      date: '2026-04-01',
      category: 'Transport',
      amount: -663.63,
      currency: 'CNY',
      notes: '',
    },
    {
      id: 'ledger-2',
      date: '2026-04-01',
      category: 'Telecom',
      amount: -6.9,
      currency: 'CNY',
      notes: '',
    },
    {
      id: 'ledger-3',
      date: '2026-04-02',
      category: 'Income',
      amount: 656.92,
      currency: 'CNY',
      notes: '',
    },
    {
      id: 'ledger-4',
      date: '2026-04-02',
      category: 'Transport',
      amount: -10557.95,
      currency: 'CNY',
      notes: '',
    },
    {
      id: 'ledger-5',
      date: '2026-04-02',
      category: 'Rent',
      amount: -10348.07,
      currency: 'CNY',
      notes: '',
    },
  ],
  forecast: [
    {
      id: 'forecast-1',
      event: 'Study / work transition',
      year: 2026,
      period: 'Apr - Aug',
      months: 5,
      tuition: 0,
      rent: 10557.97,
      utilities: 520,
      food: 3000,
      phone: 240,
      other: 2500,
      income: 83983.39,
      comment: 'Track possible income against planned expenses.',
    },
  ],
}

export function summarizeMonth(month: FinancialMonth): FinanceSummary {
  const monthCurrency = normalizeCurrencyCode(month.currency, 'CAD')
  const totalIncome = sumItems(month.income, monthCurrency)
  const passiveIncome = sumItems(
    month.income.filter((item) => normalizeIncomeCategory(item.category) === 'Passive'),
    monthCurrency,
  )
  const totalExpenses = sumItems(month.expenses, monthCurrency)
  const totalAssets = sumItems(month.assets, monthCurrency)
  const totalLiabilities = -Math.abs(sumItems(month.liabilities, monthCurrency))
  const monthlyCashFlow = roundMoney(totalIncome + totalExpenses)
  const netWorth = roundMoney(totalAssets + totalLiabilities)

  return {
    totalIncome,
    totalExpenses,
    monthlyCashFlow,
    totalAssets,
    totalLiabilities,
    netWorth,
    passiveIncome: roundMoney(passiveIncome),
    savingsRate: totalIncome ? roundPercent((monthlyCashFlow / totalIncome) * 100) : 0,
  }
}

export function summarizeLedger(entries: DailyLedgerEntry[], targetCurrency = 'CNY') {
  const currency = normalizeCurrencyCode(targetCurrency, 'CNY')
  const sumBy = (category: string) =>
    roundMoney(
      entries
        .filter((entry) => normalizeLedgerCategory(entry.category) === category)
        .reduce((sum, entry) => sum + convertCurrency(entry.amount, entry.currency || currency, currency), 0),
    )

  const income = sumBy('income')
  const expense = roundMoney(
    entries
      .filter((entry) => normalizeLedgerCategory(entry.category) !== 'income')
      .reduce((sum, entry) => sum + convertCurrency(entry.amount, entry.currency || currency, currency), 0),
  )

  return {
    income,
    expense,
    food: sumBy('food'),
    transport: sumBy('transport'),
    shopping: sumBy('shopping'),
    rent: sumBy('rent'),
  }
}

export function forecastNet(entry: ForecastEntry) {
  return roundMoney(entry.income - forecastExpense(entry))
}

export function forecastExpense(entry: ForecastEntry) {
  return roundMoney(entry.tuition + entry.rent + entry.utilities + entry.food + entry.phone + entry.other)
}

function withCurrency(
  items: Array<{ id: string; name: string; amount: number; category?: string; notes: string }>,
  currency: string,
): MoneyItem[] {
  return items.map((item) => ({ ...item, currency }))
}

export function normalizeIncomeCategory(category?: string): IncomeCategory {
  return category === 'Passive' ? 'Passive' : 'Active'
}

export function normalizeLedgerCategory(category?: string) {
  const value = (category || '').toLowerCase()
  if (value === 'income') return 'income'
  if (value === 'food') return 'food'
  if (value === 'transport') return 'transport'
  if (value === 'shopping') return 'shopping'
  if (value === 'insurance') return 'insurance'
  if (value === 'telecom') return 'telecom'
  if (value === 'utilities') return 'utilities'
  if (value === 'event') return 'event'
  if (value === 'rent') return 'rent'
  return 'expense'
}

function sumItems(items: MoneyItem[], targetCurrency: CurrencyCode) {
  return roundMoney(
    items.reduce((sum, item) => sum + convertCurrency(item.amount, item.currency || targetCurrency, targetCurrency), 0),
  )
}

function convertCurrency(value: number, sourceCurrency: string, targetCurrency: CurrencyCode): number {
  const source = normalizeCurrencyCode(sourceCurrency, targetCurrency)
  if (source === targetCurrency) return Number.isFinite(value) ? value : 0
  const valueInCny = (Number.isFinite(value) ? value : 0) * cnyPerUnit[source]
  return valueInCny / cnyPerUnit[targetCurrency]
}

function normalizeCurrencyCode(currency: string, fallback: CurrencyCode): CurrencyCode {
  if (currency === 'CAD' || currency === 'USD' || currency === 'CNY') return currency
  return fallback
}

function roundMoney(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 100) / 100
}

function roundPercent(value: number) {
  return Math.round((Number.isFinite(value) ? value : 0) * 10) / 10
}
