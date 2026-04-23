from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "fire.sqlite3"
PASSIVE_INCOME_TOKENS = (
    "interest",
    "dividend",
    "passive",
    "rent",
    "利息",
    "分红",
    "被动",
    "租金",
    "余额宝",
    "招商银行理财",
    "理财",
    "ws-cash",
    "ws-tfsa",
    "ws-rrsp",
    "ws-etf",
    "ibkr",
)
LEDGER_EXPENSE_CATEGORIES = ("food", "transport", "shopping", "insurance", "telecom", "utilities", "event", "rent")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS financial_months (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            currency TEXT NOT NULL DEFAULT 'CAD',
            passive_income REAL NOT NULL DEFAULT 0,
            conclusion TEXT NOT NULL DEFAULT '',
            source_workbook TEXT NOT NULL DEFAULT '',
            source_sheet TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS money_items (
            id TEXT PRIMARY KEY,
            month_id TEXT NOT NULL REFERENCES financial_months(id) ON DELETE CASCADE,
            section TEXT NOT NULL CHECK (section IN ('income', 'expense', 'asset', 'liability')),
            name TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'CAD',
            category TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS daily_ledger (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'CNY',
            income REAL NOT NULL DEFAULT 0,
            expense REAL NOT NULL DEFAULT 0,
            food REAL NOT NULL DEFAULT 0,
            transport REAL NOT NULL DEFAULT 0,
            shopping REAL NOT NULL DEFAULT 0,
            insurance REAL NOT NULL DEFAULT 0,
            telecom REAL NOT NULL DEFAULT 0,
            utilities REAL NOT NULL DEFAULT 0,
            event REAL NOT NULL DEFAULT 0,
            rent REAL NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            source_workbook TEXT NOT NULL DEFAULT '',
            source_sheet TEXT NOT NULL DEFAULT '',
            source_row INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS forecast_entries (
            id TEXT PRIMARY KEY,
            event TEXT NOT NULL DEFAULT '',
            year INTEGER NOT NULL DEFAULT 0,
            period TEXT NOT NULL DEFAULT '',
            months REAL NOT NULL DEFAULT 0,
            tuition REAL NOT NULL DEFAULT 0,
            rent REAL NOT NULL DEFAULT 0,
            utilities REAL NOT NULL DEFAULT 0,
            food REAL NOT NULL DEFAULT 0,
            phone REAL NOT NULL DEFAULT 0,
            other REAL NOT NULL DEFAULT 0,
            income REAL NOT NULL DEFAULT 0,
            comment TEXT NOT NULL DEFAULT '',
            source_workbook TEXT NOT NULL DEFAULT '',
            source_sheet TEXT NOT NULL DEFAULT '',
            source_row INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS raw_sheet_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workbook TEXT NOT NULL,
            sheet TEXT NOT NULL,
            row_index INTEGER NOT NULL,
            cells_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS investment_snapshots (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL UNIQUE,
            currency TEXT NOT NULL DEFAULT 'CAD',
            notes TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS investment_items (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL REFERENCES investment_snapshots(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            symbol TEXT NOT NULL DEFAULT '',
            account TEXT NOT NULL DEFAULT '',
            item_type TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            shares REAL NOT NULL DEFAULT 0,
            unit_price REAL NOT NULL DEFAULT 0,
            cost_basis REAL NOT NULL DEFAULT 0,
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'CAD',
            notes TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL UNIQUE,
            currency TEXT NOT NULL DEFAULT 'CAD',
            notes TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS portfolio_items (
            id TEXT PRIMARY KEY,
            snapshot_id TEXT NOT NULL REFERENCES portfolio_snapshots(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            symbol TEXT NOT NULL DEFAULT '',
            account TEXT NOT NULL DEFAULT '',
            item_type TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            shares REAL NOT NULL DEFAULT 0,
            unit_price REAL NOT NULL DEFAULT 0,
            cost_basis REAL NOT NULL DEFAULT 0,
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'CAD',
            notes TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    investment_item_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(investment_items)").fetchall()
    }
    if "currency" not in investment_item_columns:
        conn.execute("ALTER TABLE investment_items ADD COLUMN currency TEXT NOT NULL DEFAULT 'CAD'")
        conn.execute(
            """
            UPDATE investment_items
            SET currency = (
                SELECT investment_snapshots.currency
                FROM investment_snapshots
                WHERE investment_snapshots.id = investment_items.snapshot_id
            )
            WHERE EXISTS (
                SELECT 1
                FROM investment_snapshots
                WHERE investment_snapshots.id = investment_items.snapshot_id
            )
            """
        )
    if "item_type" not in investment_item_columns:
        conn.execute("ALTER TABLE investment_items ADD COLUMN item_type TEXT NOT NULL DEFAULT ''")
    if "symbol" not in investment_item_columns:
        conn.execute("ALTER TABLE investment_items ADD COLUMN symbol TEXT NOT NULL DEFAULT ''")
    if "shares" not in investment_item_columns:
        conn.execute("ALTER TABLE investment_items ADD COLUMN shares REAL NOT NULL DEFAULT 0")
    if "unit_price" not in investment_item_columns:
        conn.execute("ALTER TABLE investment_items ADD COLUMN unit_price REAL NOT NULL DEFAULT 0")
    if "cost_basis" not in investment_item_columns:
        conn.execute("ALTER TABLE investment_items ADD COLUMN cost_basis REAL NOT NULL DEFAULT 0")
        conn.execute(
            """
            UPDATE investment_items
            SET cost_basis = unit_price
            WHERE abs(cost_basis) <= 1e-9 AND abs(unit_price) > 1e-9
            """
        )
    portfolio_item_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(portfolio_items)").fetchall()
    }
    if "currency" not in portfolio_item_columns:
        conn.execute("ALTER TABLE portfolio_items ADD COLUMN currency TEXT NOT NULL DEFAULT 'CAD'")
        conn.execute(
            """
            UPDATE portfolio_items
            SET currency = (
                SELECT portfolio_snapshots.currency
                FROM portfolio_snapshots
                WHERE portfolio_snapshots.id = portfolio_items.snapshot_id
            )
            WHERE EXISTS (
                SELECT 1
                FROM portfolio_snapshots
                WHERE portfolio_snapshots.id = portfolio_items.snapshot_id
            )
            """
        )
    if "item_type" not in portfolio_item_columns:
        conn.execute("ALTER TABLE portfolio_items ADD COLUMN item_type TEXT NOT NULL DEFAULT ''")
    if "symbol" not in portfolio_item_columns:
        conn.execute("ALTER TABLE portfolio_items ADD COLUMN symbol TEXT NOT NULL DEFAULT ''")
    if "shares" not in portfolio_item_columns:
        conn.execute("ALTER TABLE portfolio_items ADD COLUMN shares REAL NOT NULL DEFAULT 0")
    if "unit_price" not in portfolio_item_columns:
        conn.execute("ALTER TABLE portfolio_items ADD COLUMN unit_price REAL NOT NULL DEFAULT 0")
    if "cost_basis" not in portfolio_item_columns:
        conn.execute("ALTER TABLE portfolio_items ADD COLUMN cost_basis REAL NOT NULL DEFAULT 0")
        conn.execute(
            """
            UPDATE portfolio_items
            SET cost_basis = unit_price
            WHERE abs(cost_basis) <= 1e-9 AND abs(unit_price) > 1e-9
            """
        )
    conn.execute(
        """
        UPDATE investment_items
        SET amount = shares * unit_price * 100
        WHERE lower(item_type) = 'option'
          AND abs(shares) > 1e-9
          AND abs(unit_price) > 1e-9
          AND abs(amount - (shares * unit_price)) <= 1e-6
        """
    )
    conn.execute(
        """
        UPDATE portfolio_items
        SET amount = shares * unit_price * 100
        WHERE lower(item_type) = 'option'
          AND abs(shares) > 1e-9
          AND abs(unit_price) > 1e-9
          AND abs(amount - (shares * unit_price)) <= 1e-6
        """
    )
    money_item_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(money_items)").fetchall()
    }
    if "currency" not in money_item_columns:
        conn.execute("ALTER TABLE money_items ADD COLUMN currency TEXT NOT NULL DEFAULT 'CAD'")
        conn.execute(
            """
            UPDATE money_items
            SET currency = (
                SELECT financial_months.currency
                FROM financial_months
                WHERE financial_months.id = money_items.month_id
            )
            WHERE EXISTS (
                SELECT 1
                FROM financial_months
                WHERE financial_months.id = money_items.month_id
            )
            """
        )
    if "category" not in money_item_columns:
        conn.execute("ALTER TABLE money_items ADD COLUMN category TEXT NOT NULL DEFAULT ''")
        conn.execute(
            """
            UPDATE money_items
            SET category = CASE
                WHEN section <> 'income' THEN ''
                WHEN lower(name) LIKE '%interest%'
                  OR lower(name) LIKE '%dividend%'
                  OR lower(name) LIKE '%passive%'
                  OR lower(name) LIKE '%rent%'
                  OR name LIKE '%利息%'
                  OR name LIKE '%分红%'
                  OR name LIKE '%被动%'
                  OR name LIKE '%租金%'
                THEN 'Passive'
                ELSE 'Active'
            END
            """
        )
    daily_ledger_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(daily_ledger)").fetchall()
    }
    if "category" not in daily_ledger_columns:
        conn.execute("ALTER TABLE daily_ledger ADD COLUMN category TEXT NOT NULL DEFAULT ''")
    if "amount" not in daily_ledger_columns:
        conn.execute("ALTER TABLE daily_ledger ADD COLUMN amount REAL NOT NULL DEFAULT 0")
    if "currency" not in daily_ledger_columns:
        conn.execute("ALTER TABLE daily_ledger ADD COLUMN currency TEXT NOT NULL DEFAULT 'CNY'")
    conn.commit()


def load_finance_state(conn: sqlite3.Connection) -> dict[str, Any]:
    months = []
    month_rows = conn.execute("SELECT * FROM financial_months ORDER BY label DESC").fetchall()
    for month in month_rows:
        items = conn.execute(
            "SELECT * FROM money_items WHERE month_id = ? ORDER BY section, position, name",
            (month["id"],),
        ).fetchall()
        grouped = {"income": [], "expenses": [], "assets": [], "liabilities": []}
        for item in items:
            key = {
                "income": "income",
                "expense": "expenses",
                "asset": "assets",
                "liability": "liabilities",
            }[item["section"]]
            grouped[key].append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "amount": item["amount"],
                    "currency": item["currency"] or month["currency"],
                    "category": (
                        item["category"]
                        if item["section"] == "income" and item["category"] in {"Active", "Passive"}
                        else infer_income_category(item["name"])
                    )
                    if item["section"] == "income"
                    else "",
                    "notes": item["notes"],
                }
            )
        months.append(
            {
                "id": month["id"],
                "label": month["label"],
                "currency": month["currency"],
                "passiveIncome": month["passive_income"],
                "conclusion": month["conclusion"],
                **grouped,
            }
        )

    ledger_rows = conn.execute("SELECT * FROM daily_ledger ORDER BY date DESC, source_row DESC").fetchall()
    legacy_generated_bases_with_detailed_expense: set[str] = set()
    for row in ledger_rows:
        parsed = parse_legacy_generated_ledger_id(row["id"])
        category = normalize_ledger_category(row["category"])
        if not parsed or category not in LEDGER_EXPENSE_CATEGORIES:
            continue
        base_id, parsed_category = parsed
        if parsed_category == category:
            legacy_generated_bases_with_detailed_expense.add(base_id)

    ledger: list[dict[str, Any]] = []
    for row in ledger_rows:
        category = normalize_ledger_category(row["category"])
        if category:
            parsed = parse_legacy_generated_ledger_id(row["id"])
            if category == "expense" and parsed:
                base_id, parsed_category = parsed
                if (
                    parsed_category == "expense"
                    and base_id in legacy_generated_bases_with_detailed_expense
                ):
                    continue
            amount = float(row["amount"] or 0)
            if amount == 0:
                amount = ledger_event_amount_for_category(row, category)
            ledger.append(
                {
                    "id": row["id"],
                    "date": row["date"],
                    "category": category.title(),
                    "amount": amount,
                    "currency": normalize_currency(row["currency"], "CNY"),
                    "notes": row["notes"],
                }
            )
            continue

        ledger.extend(expand_legacy_ledger_events(row))

    forecast = [
        {
            "id": row["id"],
            "event": row["event"],
            "year": row["year"],
            "period": row["period"],
            "months": row["months"],
            "tuition": row["tuition"],
            "rent": row["rent"],
            "utilities": row["utilities"],
            "food": row["food"],
            "phone": row["phone"],
            "other": row["other"],
            "income": row["income"],
            "comment": row["comment"],
        }
        for row in conn.execute("SELECT * FROM forecast_entries ORDER BY year, source_row").fetchall()
    ]

    return {"months": months, "ledger": ledger, "forecast": forecast}


def save_finance_state(conn: sqlite3.Connection, state: dict[str, Any]) -> None:
    conn.execute("DELETE FROM money_items")
    conn.execute("DELETE FROM financial_months")
    conn.execute("DELETE FROM daily_ledger")
    conn.execute("DELETE FROM forecast_entries")

    for month in state.get("months", []):
        conn.execute(
            """
            INSERT INTO financial_months
              (id, label, currency, passive_income, conclusion)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                month["id"],
                month["label"],
                month.get("currency", "CAD"),
                float(month.get("passiveIncome") or 0),
                month.get("conclusion", ""),
            ),
        )
        for section, key in [
            ("income", "income"),
            ("expense", "expenses"),
            ("asset", "assets"),
            ("liability", "liabilities"),
        ]:
            for position, item in enumerate(month.get(key, [])):
                conn.execute(
                    """
                    INSERT INTO money_items
                      (id, month_id, section, name, amount, currency, category, notes, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"],
                        month["id"],
                        section,
                        item.get("name", ""),
                        float(item.get("amount") or 0),
                        item.get("currency", month.get("currency", "CAD")),
                        ("Passive" if item.get("category") == "Passive" else infer_income_category(item.get("name", "")))
                        if section == "income"
                        else "",
                        item.get("notes", ""),
                        position,
                    ),
                )

    for row in state.get("ledger", []):
        date_value = row.get("date", "")
        if isinstance(date_value, dict):
            date_value = str(date_value.get("date", ""))
        else:
            date_value = str(date_value or "")
        category_value = row.get("category")
        if isinstance(category_value, dict):
            category_value = category_value.get("label") or category_value.get("value") or ""
        category = normalize_ledger_category(str(category_value))
        currency_value = row.get("currency", "CNY")
        if isinstance(currency_value, dict):
            currency_value = currency_value.get("label") or currency_value.get("value") or ""
        currency = normalize_currency(str(currency_value), "CNY")
        amount = float(row.get("amount") or 0)
        income = amount if category == "income" else 0.0
        expense = amount if category != "income" else 0.0
        conn.execute(
            """
            INSERT INTO daily_ledger
              (id, date, category, amount, currency, income, expense, food, transport, shopping, insurance, telecom, utilities, event, rent, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                date_value,
                category.title() if category else "",
                amount,
                currency,
                income,
                expense,
                amount if category == "food" else 0,
                amount if category == "transport" else 0,
                amount if category == "shopping" else 0,
                amount if category == "insurance" else 0,
                amount if category == "telecom" else 0,
                amount if category == "utilities" else 0,
                amount if category == "event" else 0,
                amount if category == "rent" else 0,
                row.get("notes", ""),
            ),
        )

    for row in state.get("forecast", []):
        conn.execute(
            """
            INSERT INTO forecast_entries
              (id, event, year, period, months, tuition, rent, utilities, food, phone, other, income, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row.get("event", ""),
                int(row.get("year") or 0),
                row.get("period", ""),
                float(row.get("months") or 0),
                float(row.get("tuition") or 0),
                float(row.get("rent") or 0),
                float(row.get("utilities") or 0),
                float(row.get("food") or 0),
                float(row.get("phone") or 0),
                float(row.get("other") or 0),
                float(row.get("income") or 0),
                row.get("comment", ""),
            ),
        )
    conn.commit()


def insert_raw_row(conn: sqlite3.Connection, workbook: str, sheet: str, row_index: int, cells: list[Any]) -> None:
    conn.execute(
        "INSERT INTO raw_sheet_rows (workbook, sheet, row_index, cells_json) VALUES (?, ?, ?, ?)",
        (workbook, sheet, row_index, json.dumps(cells, ensure_ascii=False)),
    )


def infer_income_category(name: str) -> str:
    lower_name = (name or "").lower()
    if any(token in lower_name for token in PASSIVE_INCOME_TOKENS):
        return "Passive"
    return "Active"


def normalize_ledger_category(category: str | None) -> str:
    value = (category or "").strip().lower()
    if value in {"income", *LEDGER_EXPENSE_CATEGORIES, "expense"}:
        return value
    return ""


def normalize_currency(currency: str | None, fallback: str = "CNY") -> str:
    value = (currency or "").strip().upper()
    if value in {"CNY", "CAD", "USD"}:
        return value
    return fallback


def normalize_investment_type(item_type: str | None, name: str | None = "") -> str:
    value = (item_type or "").strip().lower()
    if value in {"cash", "stock", "etf", "option", "bond", "crypto", "fund", "other"}:
        return value.upper() if value == "etf" else value.title()

    name_value = (name or "").strip().lower()
    if any(token in name_value for token in ("cash", "bank", "savings", "wallet")):
        return "Cash"
    if any(token in name_value for token in ("etf", "index")):
        return "ETF"
    if any(token in name_value for token in ("option", "call", "put")):
        return "Option"
    if any(token in name_value for token in ("bond", "treasury")):
        return "Bond"
    if any(token in name_value for token in ("crypto", "btc", "eth")):
        return "Crypto"
    if any(token in name_value for token in ("fund", "mutual")):
        return "Fund"
    if any(token in name_value for token in ("stock", "equity", "share")):
        return "Stock"
    return "Other"


def is_share_based_type(item_type: str | None) -> bool:
    value = normalize_investment_type(item_type)
    return value in {"Stock", "ETF", "Option", "Crypto", "Bond", "Fund"}


def investment_contract_multiplier(item_type: str | None) -> float:
    value = normalize_investment_type(item_type)
    if value == "Option":
        return 100.0
    return 1.0


def parse_legacy_generated_ledger_id(entry_id: str | None) -> tuple[str, str] | None:
    value = (entry_id or "").strip()
    parts = value.rsplit(":", 2)
    if len(parts) != 3:
        return None
    base_id, category, index = parts
    if not base_id or not index.isdigit():
        return None
    parsed_category = normalize_ledger_category(category)
    if not parsed_category:
        return None
    return base_id, parsed_category


def ledger_event_amount_for_category(row: sqlite3.Row, category: str) -> float:
    if category == "income":
        return float(row["income"] or 0)
    if category == "expense":
        return float(row["expense"] or 0)
    if category in LEDGER_EXPENSE_CATEGORIES:
        return float(row[category] or 0)
    return 0.0


def expand_legacy_ledger_events(row: sqlite3.Row) -> list[dict[str, Any]]:
    events: list[tuple[str, float]] = []
    income_amount = float(row["income"] or 0)
    if abs(income_amount) > 1e-9:
        events.append(("income", income_amount))

    detailed_expense_sum = 0.0
    for category in LEDGER_EXPENSE_CATEGORIES:
        amount = float(row[category] or 0)
        if abs(amount) > 1e-9:
            events.append((category, amount))
            detailed_expense_sum += amount

    expense_amount = float(row["expense"] or 0)
    if abs(detailed_expense_sum) <= 1e-9 and abs(expense_amount) > 1e-9:
        events.append(("expense", expense_amount))

    if not events:
        return []

    if len(events) == 1:
        category, amount = events[0]
        return [
            {
                "id": row["id"],
                "date": row["date"],
                "category": category.title(),
                "amount": amount,
                "currency": normalize_currency(row["currency"], "CNY"),
                "notes": row["notes"],
            }
        ]

    return [
        {
            "id": f'{row["id"]}:{category}:{index}',
            "date": row["date"],
            "category": category.title(),
            "amount": amount,
            "currency": normalize_currency(row["currency"], "CNY"),
            "notes": row["notes"],
        }
        for index, (category, amount) in enumerate(events, start=1)
    ]


def load_investment_state(conn: sqlite3.Connection) -> dict[str, Any]:
    return _load_snapshot_state(conn, "investment_snapshots", "investment_items")


def save_investment_state(conn: sqlite3.Connection, state: dict[str, Any]) -> None:
    _save_snapshot_state(conn, state, "investment_snapshots", "investment_items")


def load_portfolio_state(conn: sqlite3.Connection) -> dict[str, Any]:
    return _load_snapshot_state(conn, "portfolio_snapshots", "portfolio_items")


def save_portfolio_state(conn: sqlite3.Connection, state: dict[str, Any]) -> None:
    _save_snapshot_state(conn, state, "portfolio_snapshots", "portfolio_items")


def _load_snapshot_state(conn: sqlite3.Connection, snapshot_table: str, item_table: str) -> dict[str, Any]:
    snapshots = []
    rows = conn.execute(f"SELECT * FROM {snapshot_table} ORDER BY date DESC").fetchall()
    for snapshot in rows:
        items = conn.execute(
            f"SELECT * FROM {item_table} WHERE snapshot_id = ? ORDER BY position, name",
            (snapshot["id"],),
        ).fetchall()
        snapshots.append(
            {
                "id": snapshot["id"],
                "date": snapshot["date"],
                "currency": snapshot["currency"],
                "notes": snapshot["notes"],
                "items": [
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "symbol": item["symbol"],
                        "account": item["account"],
                        "type": normalize_investment_type(item["item_type"], item["name"]),
                        "category": item["category"],
                        "shares": float(item["shares"] or 0),
                        "unitPrice": float(item["unit_price"] or 0),
                        "costBasis": float(item["cost_basis"] or 0),
                        "amount": item["amount"],
                        "currency": item["currency"] or snapshot["currency"],
                        "notes": item["notes"],
                    }
                    for item in items
                ],
            }
        )
    return {"snapshots": snapshots}


def _save_snapshot_state(conn: sqlite3.Connection, state: dict[str, Any], snapshot_table: str, item_table: str) -> None:
    conn.execute(f"DELETE FROM {item_table}")
    conn.execute(f"DELETE FROM {snapshot_table}")
    for snapshot in state.get("snapshots", []):
        conn.execute(
            f"""
            INSERT INTO {snapshot_table} (id, date, currency, notes)
            VALUES (?, ?, ?, ?)
            """,
            (
                snapshot["id"],
                snapshot["date"],
                snapshot.get("currency", "CAD"),
                snapshot.get("notes", ""),
            ),
        )
        for position, item in enumerate(snapshot.get("items", [])):
            item_type = normalize_investment_type(item.get("type", ""), item.get("name", ""))
            shares = float(item.get("shares") or 0)
            unit_price = float(item.get("unitPrice") or item.get("unit_price") or 0)
            input_cost_basis = float(item.get("costBasis") or item.get("cost_basis") or 0)
            input_amount = float(item.get("amount") or 0)
            multiplier = investment_contract_multiplier(item_type)
            computed_amount = shares * unit_price * multiplier
            amount = computed_amount if is_share_based_type(item_type) and abs(computed_amount) > 1e-9 else input_amount
            if is_share_based_type(item_type):
                cost_basis = input_cost_basis if abs(input_cost_basis) > 1e-9 else unit_price
            else:
                cost_basis = input_cost_basis if abs(input_cost_basis) > 1e-9 else input_amount
            conn.execute(
                f"""
                INSERT INTO {item_table}
                  (id, snapshot_id, name, symbol, account, item_type, category, shares, unit_price, cost_basis, amount, currency, notes, position)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    snapshot["id"],
                    item.get("name", ""),
                    item.get("symbol", ""),
                    item.get("account", ""),
                    item_type,
                    item.get("category", ""),
                    shares,
                    unit_price,
                    cost_basis,
                    amount,
                    item.get("currency") or snapshot.get("currency", "CAD"),
                    item.get("notes", ""),
                    position,
                ),
            )
    conn.commit()
