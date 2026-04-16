from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "fire.sqlite3"


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
            notes TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS daily_ledger (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
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
            account TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            amount REAL NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0
        );
        """
    )
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

    ledger = [
        {
            "id": row["id"],
            "date": row["date"],
            "income": row["income"],
            "expense": row["expense"],
            "food": row["food"],
            "transport": row["transport"],
            "shopping": row["shopping"],
            "insurance": row["insurance"],
            "telecom": row["telecom"],
            "utilities": row["utilities"],
            "event": row["event"],
            "rent": row["rent"],
            "notes": row["notes"],
        }
        for row in conn.execute("SELECT * FROM daily_ledger ORDER BY date DESC, source_row DESC").fetchall()
    ]

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
                      (id, month_id, section, name, amount, notes, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"],
                        month["id"],
                        section,
                        item.get("name", ""),
                        float(item.get("amount") or 0),
                        item.get("notes", ""),
                        position,
                    ),
                )

    for row in state.get("ledger", []):
        conn.execute(
            """
            INSERT INTO daily_ledger
              (id, date, income, expense, food, transport, shopping, insurance, telecom, utilities, event, rent, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["date"],
                float(row.get("income") or 0),
                float(row.get("expense") or 0),
                float(row.get("food") or 0),
                float(row.get("transport") or 0),
                float(row.get("shopping") or 0),
                float(row.get("insurance") or 0),
                float(row.get("telecom") or 0),
                float(row.get("utilities") or 0),
                float(row.get("event") or 0),
                float(row.get("rent") or 0),
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


def load_investment_state(conn: sqlite3.Connection) -> dict[str, Any]:
    snapshots = []
    rows = conn.execute("SELECT * FROM investment_snapshots ORDER BY date DESC").fetchall()
    for snapshot in rows:
        items = conn.execute(
            "SELECT * FROM investment_items WHERE snapshot_id = ? ORDER BY position, name",
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
                        "account": item["account"],
                        "category": item["category"],
                        "amount": item["amount"],
                        "notes": item["notes"],
                    }
                    for item in items
                ],
            }
        )
    return {"snapshots": snapshots}


def save_investment_state(conn: sqlite3.Connection, state: dict[str, Any]) -> None:
    conn.execute("DELETE FROM investment_items")
    conn.execute("DELETE FROM investment_snapshots")
    for snapshot in state.get("snapshots", []):
        conn.execute(
            """
            INSERT INTO investment_snapshots (id, date, currency, notes)
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
            conn.execute(
                """
                INSERT INTO investment_items
                  (id, snapshot_id, name, account, category, amount, notes, position)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    snapshot["id"],
                    item.get("name", ""),
                    item.get("account", ""),
                    item.get("category", ""),
                    float(item.get("amount") or 0),
                    item.get("notes", ""),
                    position,
                ),
            )
    conn.commit()
