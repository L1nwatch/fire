from __future__ import annotations

import json
import re
from datetime import date
from csv import DictReader
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import (
    connect,
    init_db,
    load_finance_state,
    load_investment_state,
    load_portfolio_state,
    save_finance_state,
    save_investment_state,
    save_portfolio_state,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

app = FastAPI(title="Fire")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    with connect() as conn:
        init_db(conn)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/finance")
def get_finance() -> dict[str, Any]:
    with connect() as conn:
        init_db(conn)
        return load_finance_state(conn)


@app.put("/api/finance")
def put_finance(state: dict[str, Any]) -> dict[str, bool]:
    with connect() as conn:
        init_db(conn)
        save_finance_state(conn, state)
    return {"ok": True}


@app.get("/api/investments")
def get_investments() -> dict[str, Any]:
    with connect() as conn:
        init_db(conn)
        return load_investment_state(conn)


@app.put("/api/investments")
def put_investments(state: dict[str, Any]) -> dict[str, bool]:
    with connect() as conn:
        init_db(conn)
        save_investment_state(conn, state)
    return {"ok": True}


@app.get("/api/portfolio")
def get_portfolio() -> dict[str, Any]:
    with connect() as conn:
        init_db(conn)
        return load_portfolio_state(conn)


@app.put("/api/portfolio")
def put_portfolio(state: dict[str, Any]) -> dict[str, bool]:
    with connect() as conn:
        init_db(conn)
        save_portfolio_state(conn, state)
    return {"ok": True}


@app.get("/api/market/quote")
def get_market_quote(symbol: str) -> dict[str, Any]:
    normalized = (symbol or "").strip().upper()
    if not normalized:
        raise HTTPException(status_code=400, detail="Symbol is required")

    provider_order = [_fetch_yahoo_quote, _fetch_stooq_quote, _fetch_tmx_quote]
    if _is_occ_option_symbol(normalized):
        # For full option contract symbols, try Nasdaq option-chain delayed quote first.
        provider_order = [_fetch_nasdaq_option_quote, _fetch_yahoo_quote, _fetch_stooq_quote, _fetch_tmx_quote]
    if normalized.endswith((".CA", ".TO", ".TSX")):
        # For Canadian symbols, prefer TMX over Stooq to avoid US cross-listing mismatches.
        provider_order = [_fetch_yahoo_quote, _fetch_tmx_quote, _fetch_stooq_quote]

    errors: list[str] = []
    for fetcher in provider_order:
        try:
            return fetcher(normalized)
        except HTTPException as error:
            errors.append(str(error.detail))

    raise HTTPException(status_code=502, detail=f"Quote fetch failed ({'; '.join(errors)})")


def _fetch_yahoo_quote(symbol: str) -> dict[str, Any]:
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={quote_plus(symbol)}"
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 FireApp/1.0",
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise HTTPException(status_code=502, detail=f"Quote provider error: {error.code}") from error
    except URLError as error:
        raise HTTPException(status_code=502, detail=f"Quote provider unavailable: {error.reason}") from error
    except Exception as error:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail="Failed to fetch quote") from error

    results = payload.get("quoteResponse", {}).get("result", [])
    if not results:
        raise HTTPException(status_code=404, detail=f"No quote found for {symbol}")

    quote = results[0]
    price = quote.get("regularMarketPrice")
    if price is None:
        raise HTTPException(status_code=404, detail=f"No market price for {symbol}")

    return {
        "symbol": quote.get("symbol", symbol),
        "price": float(price),
        "currency": quote.get("currency", "USD"),
        "source": "Yahoo Finance",
    }


def _fetch_stooq_quote(symbol: str) -> dict[str, Any]:
    stooq_symbol = symbol.lower()
    if "." not in stooq_symbol:
        stooq_symbol = f"{stooq_symbol}.us"
    url = f"https://stooq.com/q/l/?s={quote_plus(stooq_symbol)}&f=sd2t2ohlcv&h&e=csv"
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 FireApp/1.0", "Accept": "text/csv"})
        with urlopen(request, timeout=8) as response:
            text = response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        raise HTTPException(status_code=502, detail=f"Stooq provider error: {error.code}") from error
    except URLError as error:
        raise HTTPException(status_code=502, detail=f"Stooq provider unavailable: {error.reason}") from error
    except Exception as error:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail="Failed to fetch quote from stooq") from error

    rows = list(DictReader(StringIO(text)))
    if not rows:
        raise HTTPException(status_code=404, detail=f"No stooq quote found for {symbol}")

    row = rows[0]
    close_value = row.get("Close", "").strip()
    symbol_value = row.get("Symbol", "").strip().upper()
    if not close_value or close_value.lower() == "n/a":
        raise HTTPException(status_code=404, detail=f"No stooq market price for {symbol}")

    try:
        price = float(close_value)
    except ValueError as error:
        raise HTTPException(status_code=502, detail=f"Invalid stooq price for {symbol}") from error

    # Stooq does not provide currency in this endpoint, defaulting to USD.
    return {
        "symbol": symbol_value or symbol,
        "price": price,
        "currency": "USD",
        "source": "Stooq",
    }


def _fetch_tmx_quote(symbol: str) -> dict[str, Any]:
    tmx_symbol = _normalize_symbol_for_tmx(symbol)
    if not tmx_symbol:
        raise HTTPException(status_code=404, detail=f"TMX symbol not supported for {symbol}")

    url = f"https://r.jina.ai/http://money.tmx.com/en/quote/{quote_plus(tmx_symbol)}"
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 FireApp/1.0", "Accept": "text/plain"})
        with urlopen(request, timeout=8) as response:
            text = response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        raise HTTPException(status_code=502, detail=f"TMX provider error: {error.code}") from error
    except URLError as error:
        raise HTTPException(status_code=502, detail=f"TMX provider unavailable: {error.reason}") from error
    except Exception as error:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail="Failed to fetch quote from TMX") from error

    price = _extract_tmx_price(text, symbol)
    parsed_symbol = _extract_tmx_symbol(text) or tmx_symbol
    exchange = _extract_tmx_exchange(text)

    return {
        "symbol": parsed_symbol,
        "price": price,
        "currency": "CAD" if exchange == "TSX" else "USD",
        "source": "TMX Money",
    }


def _fetch_nasdaq_option_quote(symbol: str) -> dict[str, Any]:
    parsed = _parse_occ_option_symbol(symbol)
    if not parsed:
        raise HTTPException(status_code=404, detail=f"Invalid OCC option symbol: {symbol}")

    underlying = parsed["underlying"]
    expiry = parsed["expiry"]
    strike = parsed["strike"]
    option_side = parsed["side"]

    requests = [
        (
            "etf",
            f"https://api.nasdaq.com/api/quote/{quote_plus(underlying)}/option-chain"
            f"?assetclass=etf&fromdate={expiry.isoformat()}&todate={expiry.isoformat()}"
            f"&strikeprice={strike:.3f}&callput={option_side}",
        ),
        (
            "stocks",
            f"https://api.nasdaq.com/api/quote/{quote_plus(underlying)}/option-chain"
            f"?assetclass=stocks&fromdate={expiry.isoformat()}&todate={expiry.isoformat()}"
            f"&strikeprice={strike:.3f}&callput={option_side}",
        ),
    ]

    last_error: HTTPException | None = None
    for _, url in requests:
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 FireApp/1.0",
                    "Accept": "application/json",
                },
            )
            with urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            price = _extract_nasdaq_option_price(payload, strike, option_side)
            return {
                "symbol": symbol,
                "price": price,
                "currency": "USD",
                "source": "Nasdaq Options",
            }
        except HTTPException as error:
            last_error = error
            continue
        except HTTPError as error:
            last_error = HTTPException(status_code=502, detail=f"Nasdaq options provider error: {error.code}")
            continue
        except URLError as error:
            last_error = HTTPException(status_code=502, detail=f"Nasdaq options provider unavailable: {error.reason}")
            continue
        except Exception as error:  # pragma: no cover - defensive
            last_error = HTTPException(status_code=502, detail=f"Failed to fetch options quote: {error}")
            continue

    if last_error is not None:
        raise last_error
    raise HTTPException(status_code=404, detail=f"No Nasdaq option quote found for {symbol}")


def _normalize_symbol_for_tmx(symbol: str) -> str | None:
    candidate = symbol.strip().upper()
    if not candidate:
        return None

    for suffix in (".TO", ".TSX", ".CA"):
        if candidate.endswith(suffix):
            candidate = candidate[: -len(suffix)]
            break

    if not candidate:
        return None
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9\-.]{0,9}", candidate):
        return None
    return candidate


def _extract_tmx_price(text: str, symbol: str) -> float:
    patterns = (
        r"Price:\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
        r"\n\$([0-9][0-9,]*(?:\.[0-9]+)?)\n",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        raw_price = match.group(1).replace(",", "")
        try:
            return float(raw_price)
        except ValueError:
            continue
    raise HTTPException(status_code=404, detail=f"No TMX market price for {symbol}")


def _extract_tmx_symbol(text: str) -> str | None:
    title_match = re.search(r"\(([A-Z0-9.\-]{1,12})\)\s*\|\s*TSX Stock Price", text)
    if title_match:
        return title_match.group(1)

    block_match = re.search(r"\n([A-Z0-9.\-]{1,12})\n\nExchange:\s*\n*\s*TSX\b", text)
    if block_match:
        return block_match.group(1)
    return None


def _extract_tmx_exchange(text: str) -> str | None:
    match = re.search(r"Exchange:\s*\n*\s*([A-Z]+)\b", text)
    if not match:
        return None
    return match.group(1).upper()


def _is_occ_option_symbol(symbol: str) -> bool:
    return _parse_occ_option_symbol(symbol) is not None


def _parse_occ_option_symbol(symbol: str) -> dict[str, Any] | None:
    match = re.fullmatch(r"([A-Z]{1,6})(\d{2})(\d{2})(\d{2})([CP])(\d{8})", symbol.strip().upper())
    if not match:
        return None
    underlying = match.group(1)
    yy = int(match.group(2))
    mm = int(match.group(3))
    dd = int(match.group(4))
    side = "call" if match.group(5) == "C" else "put"
    strike = int(match.group(6)) / 1000.0
    try:
        expiry = date(2000 + yy, mm, dd)
    except ValueError:
        return None
    return {
        "underlying": underlying,
        "expiry": expiry,
        "side": side,
        "strike": strike,
    }


def _extract_nasdaq_option_price(payload: dict[str, Any], strike: float, option_side: str) -> float:
    rows = payload.get("data", {}).get("table", {}).get("rows", [])
    if not isinstance(rows, list):
        raise HTTPException(status_code=404, detail="No option rows in Nasdaq response")

    target_key = "p" if option_side == "put" else "c"
    strike_match: dict[str, Any] | None = None
    for row in rows:
        row_strike = _parse_numeric(row.get("strike"))
        if row_strike is None:
            continue
        if abs(row_strike - strike) <= 1e-6:
            strike_match = row
            break
    if strike_match is None:
        raise HTTPException(status_code=404, detail=f"No Nasdaq option row for strike {strike:.3f}")

    last_value = _parse_numeric(strike_match.get(f"{target_key}_Last"))
    if last_value is not None and last_value > 0:
        return float(last_value)

    bid = _parse_numeric(strike_match.get(f"{target_key}_Bid"))
    ask = _parse_numeric(strike_match.get(f"{target_key}_Ask"))
    if bid is not None and ask is not None and bid > 0 and ask > 0:
        return float((bid + ask) / 2.0)
    if bid is not None and bid > 0:
        return float(bid)
    if ask is not None and ask > 0:
        return float(ask)
    raise HTTPException(status_code=404, detail="No valid Nasdaq option price fields")


def _parse_numeric(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text or text in {"--", "N/A", "n/a", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


assets_dir = FRONTEND_DIST / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    index_html = FRONTEND_DIST / "index.html"
    if index_html.exists():
        return FileResponse(index_html)
    return JSONResponse(
        status_code=503,
        content={"detail": "Frontend build not found. Run npm run build in frontend."},
    )
