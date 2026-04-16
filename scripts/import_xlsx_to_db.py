from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.db import connect, init_db, insert_raw_row

NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Fire initialization XLSX files into SQLite.")
    parser.add_argument("--db", type=Path, default=ROOT_DIR / "data" / "fire.sqlite3")
    parser.add_argument("workbooks", nargs="*", type=Path)
    args = parser.parse_args()

    workbooks = args.workbooks or [
        ROOT_DIR / "2023-Canada-财务记账.xlsx",
        ROOT_DIR / "财务报表.xlsx",
    ]

    with connect(args.db) as conn:
        init_db(conn)
        clear_imported_data(conn)
        for workbook in workbooks:
            import_workbook(conn, workbook)
        conn.commit()

    print(f"Imported {len(workbooks)} workbook(s) into {args.db}")


def clear_imported_data(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM money_items")
    conn.execute("DELETE FROM financial_months")
    conn.execute("DELETE FROM daily_ledger")
    conn.execute("DELETE FROM forecast_entries")
    conn.execute("DELETE FROM raw_sheet_rows")


def import_workbook(conn: sqlite3.Connection, path: Path) -> None:
    if not path.exists():
        print(f"Skipping missing workbook: {path}")
        return

    with ZipFile(path) as archive:
        shared = load_shared_strings(archive)
        for sheet_name, sheet_path in workbook_sheets(archive):
            rows = read_sheet_rows(archive, sheet_path, shared)
            for index, row in enumerate(rows, start=1):
                insert_raw_row(conn, path.name, sheet_name, index, row)

            if is_report_sheet(sheet_name, rows):
                import_report_sheet(conn, path.name, sheet_name, rows)
            elif is_daily_sheet(sheet_name, rows):
                import_daily_sheet(conn, path.name, sheet_name, rows)
            elif sheet_name == "Predict":
                import_forecast_sheet(conn, path.name, sheet_name, rows)


def import_report_sheet(conn: sqlite3.Connection, workbook: str, sheet: str, rows: list[list[Any]]) -> None:
    month_id = stable_id("month", workbook, sheet)
    passive_income = number_at(rows, 0, 9)

    conn.execute(
        """
        INSERT INTO financial_months
          (id, label, currency, passive_income, conclusion, source_workbook, source_sheet)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (month_id, normalize_month_label(sheet), "CNY", passive_income, "", workbook, sheet),
    )

    item_specs = [
        ("income", 0, 1),
        ("expense", 2, 3),
        ("asset", 4, 5),
        ("liability", 6, 7),
    ]
    for section, name_col, amount_col in item_specs:
        position = 0
        for row_index, row in enumerate(rows[1:], start=2):
            name = text_at(row, name_col)
            amount = numeric(row_value(row, amount_col))
            if not name and amount == 0:
                continue
            conn.execute(
                """
                INSERT INTO money_items
                  (id, month_id, section, name, amount, notes, position)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stable_id("item", workbook, sheet, section, row_index, name),
                    month_id,
                    section,
                    name or "(blank)",
                    amount,
                    "",
                    position,
                ),
            )
            position += 1

def import_daily_sheet(conn: sqlite3.Connection, workbook: str, sheet: str, rows: list[list[Any]]) -> None:
    for row_index, row in enumerate(rows[2:], start=3):
        date_value = excel_date(row_value(row, 0))
        if not date_value:
            continue
        if all(numeric(row_value(row, col)) == 0 for col in range(1, 11)):
            continue
        conn.execute(
            """
            INSERT INTO daily_ledger
              (id, date, income, expense, food, transport, shopping, insurance, telecom,
               utilities, event, rent, notes, source_workbook, source_sheet, source_row)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stable_id("ledger", workbook, sheet, row_index),
                date_value,
                numeric(row_value(row, 1)),
                numeric(row_value(row, 2)),
                numeric(row_value(row, 3)),
                numeric(row_value(row, 4)),
                numeric(row_value(row, 5)),
                numeric(row_value(row, 6)),
                numeric(row_value(row, 7)),
                numeric(row_value(row, 8)),
                numeric(row_value(row, 9)),
                numeric(row_value(row, 10)),
                text_at(row, 11),
                workbook,
                sheet,
                row_index,
            ),
        )


def import_forecast_sheet(conn: sqlite3.Connection, workbook: str, sheet: str, rows: list[list[Any]]) -> None:
    for row_index, row in enumerate(rows[1:], start=2):
        event = text_at(row, 0)
        if not event:
            continue
        conn.execute(
            """
            INSERT INTO forecast_entries
              (id, event, year, period, months, tuition, rent, utilities, food, phone,
               other, income, comment, source_workbook, source_sheet, source_row)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stable_id("forecast", workbook, sheet, row_index),
                event,
                int(numeric(row_value(row, 1))),
                text_at(row, 2),
                numeric(row_value(row, 3)),
                numeric(row_value(row, 4)),
                numeric(row_value(row, 5)),
                numeric(row_value(row, 6)),
                numeric(row_value(row, 7)),
                numeric(row_value(row, 8)),
                numeric(row_value(row, 9)),
                numeric(row_value(row, 10)),
                text_at(row, 11),
                workbook,
                sheet,
                row_index,
            ),
        )

def is_report_sheet(sheet: str, rows: list[list[Any]]) -> bool:
    return bool(re.fullmatch(r"\d{4}\.\d{2}", sheet)) and text_at(rows[0], 0) == "项目"


def is_daily_sheet(sheet: str, rows: list[list[Any]]) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}", sheet)) and text_at(rows[1], 0) == "日期"


def normalize_month_label(sheet: str) -> str:
    return sheet.replace(".", "-")


def summary_value(rows: list[list[Any]], label: str) -> float:
    for row in rows:
        for index, value in enumerate(row[:-1]):
            if str(value).strip() == label:
                return numeric(row[index + 1])
    return 0


def workbook_sheets(archive: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_by_id = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("rel:Relationship", REL_NS)}
    sheets = []
    for sheet in workbook.findall("a:sheets/a:sheet", NS):
        target = rel_by_id[sheet.attrib[REL_ID]]
        sheets.append((sheet.attrib["name"], "xl/" + target.lstrip("/")))
    return sheets


def load_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root.findall("a:si", NS)]


def read_sheet_rows(archive: ZipFile, sheet_path: str, shared: list[str]) -> list[list[Any]]:
    root = ET.fromstring(archive.read(sheet_path))
    rows = []
    for row in root.findall("a:sheetData/a:row", NS):
        values: list[Any] = []
        for cell in row.findall("a:c", NS):
            column = column_index(cell.attrib.get("r", "A1"))
            while len(values) < column:
                values.append("")
            values.append(cell_value(cell, shared))
        rows.append(values)
    return rows


def cell_value(cell: ET.Element, shared: list[str]) -> Any:
    value = cell.find("a:v", NS)
    inline = cell.find("a:is", NS)
    cell_type = cell.attrib.get("t")
    if cell_type == "s" and value is not None:
        index = int(value.text or 0)
        return shared[index] if index < len(shared) else ""
    if cell_type == "inlineStr" and inline is not None:
        return "".join(inline.itertext())
    if value is None or value.text is None:
        return ""
    return value.text


def column_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha())
    total = 0
    for char in letters:
        total = total * 26 + ord(char.upper()) - 64
    return max(total - 1, 0)


def row_value(row: list[Any], index: int) -> Any:
    return row[index] if index < len(row) else ""


def text_at(row: list[Any], index: int) -> str:
    value = row_value(row, index)
    if value is None:
        return ""
    return str(value).strip()


def number_at(rows: list[list[Any]], row_index: int, col_index: int) -> float:
    if row_index >= len(rows):
        return 0
    return numeric(row_value(rows[row_index], col_index))


def numeric(value: Any) -> float:
    if value in ("", None):
        return 0
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0


def excel_date(value: Any) -> str:
    number = numeric(value)
    if number <= 0:
        return ""
    return (date(1899, 12, 30) + timedelta(days=int(number))).isoformat()


def stable_id(*parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", raw).strip("-")[:180]


if __name__ == "__main__":
    main()
