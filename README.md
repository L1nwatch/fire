# Fire

Fire is a local-first finance workbook for monitoring monthly cash flow, daily spending, assets, liabilities, forecasts, and investment positions.

## Frontend

The app uses the same frontend stack as TriggerToDo:

- Vue 3
- TypeScript
- Vite
- Element Plus

Run it locally:

```bash
cd frontend
npm install
npm run dev
```

Build it:

```bash
cd frontend
npm run build
```

The initialization spreadsheets are intentionally ignored by Git. Use them as private reference data while shaping the local workbook.

## Exchange rates

Fire uses the Bank of Canada's latest daily reference rates for CAD, CNY, USD, and EUR across investment values, financial summaries, and the ledger. These are daily averages, not live trading or bank conversion quotes. Historical reports are displayed using the latest available reference rates, not transaction-date rates.

`GET /api/exchange-rates` returns CAD per unit of each currency, the observation date, source, fetch time, and a stale flag. The backend refreshes hourly and persists its last successful response in SQLite; the browser also keeps a validated cache. Failed updates retain that cache with a visible warning. Without any valid rates, the app asks for a retry instead of displaying invented converted totals.

Run the backend regression tests from `vendor/fire` with `../../.venv/bin/python -m unittest discover -s tests`. Run the frontend currency tests with `npm test` from `frontend`.
