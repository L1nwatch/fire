from __future__ import annotations

import json
import math
from contextlib import closing
from datetime import date, datetime, timezone
from threading import Lock
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.db import connect

SOURCE_URL = "https://www.bankofcanada.ca/rates/exchange/daily-exchange-rates/"
API_URL = "https://www.bankofcanada.ca/valet/observations/FXCNYCAD,FXUSDCAD,FXEURCAD/json?recent=10"
CACHE_SECONDS = 3600
_refresh_lock = Lock()


def _validate(state: dict) -> dict:
    if state["base"] != "CAD" or state["source"] != "Bank of Canada":
        raise ValueError("Unexpected exchange-rate source or base")
    date.fromisoformat(state["date"])
    fetched_at = datetime.fromisoformat(state["fetchedAt"])
    if fetched_at.tzinfo is None:
        raise ValueError("Missing timestamp timezone")
    rates = state["rates"]
    if rates["CAD"] != 1 or any(
        not math.isfinite(float(rates[code])) or float(rates[code]) <= 0
        for code in ("CAD", "CNY", "USD", "EUR")
    ):
        raise ValueError("Invalid exchange rates")
    return state


def _read_cache() -> dict | None:
    with closing(connect()) as conn, conn:
        conn.execute("CREATE TABLE IF NOT EXISTS exchange_rate_cache (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)")
        row = conn.execute("SELECT payload FROM exchange_rate_cache WHERE id = 1").fetchone()
    if row is None:
        return None
    try:
        return _validate(json.loads(row[0]))
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _write_cache(state: dict) -> None:
    with closing(connect()) as conn, conn:
        conn.execute("INSERT OR REPLACE INTO exchange_rate_cache (id, payload) VALUES (1, ?)", (json.dumps(state),))


def _fetch_rates() -> dict:
    request = Request(API_URL, headers={"Accept": "application/json", "User-Agent": "FireApp/1.0"})
    with urlopen(request, timeout=8) as response:
        payload = json.load(response)
    # All crosses must use the same observation date; skip incomplete publication rows.
    for observation in sorted(payload["observations"], key=lambda row: row.get("d", ""), reverse=True):
        try:
            state = {
                "base": "CAD",
                "rates": {"CAD": 1.0, **{code: float(observation[f"FX{code}CAD"]["v"]) for code in ("CNY", "USD", "EUR")}},
                "date": observation["d"],
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                "source": "Bank of Canada",
                "sourceUrl": SOURCE_URL,
            }
            return _validate(state)
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    raise ValueError("No complete daily exchange rates")


def get_exchange_rates() -> dict:
    with _refresh_lock:
        cached = _read_cache()
        now = datetime.now(timezone.utc)
        fresh = cached is not None and 0 <= (now - datetime.fromisoformat(cached["fetchedAt"])).total_seconds() < CACHE_SECONDS
        failed = False
        if not fresh:
            try:
                updated = _fetch_rates()
            except (OSError, KeyError, TypeError, ValueError, OverflowError):
                if cached is None:
                    raise HTTPException(status_code=503, detail="Exchange rates unavailable. Please retry shortly.") from None
                failed = True
            else:
                _write_cache(updated)
                cached = updated
        assert cached is not None
        stale = failed or (now.date() - date.fromisoformat(cached["date"])).days > 7
        return {**cached, "stale": stale}
