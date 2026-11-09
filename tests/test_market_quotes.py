import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from fastapi import HTTPException

from app.main import _normalize_market_symbol, _normalize_symbol_for_tmx, get_market_quote


class NvidiaQuoteTests(unittest.TestCase):
    def test_canadian_cdr_aliases_resolve_to_tsx_listing(self):
        for symbol in ("NVDA.TO", " nvda.to ", "NVDA.CA", "NVDA.TSX", "NVDA.NE"):
            with self.subTest(symbol=symbol):
                self.assertEqual(_normalize_market_symbol(symbol), "NVDA.TO")

    def test_us_stock_aliases_keep_us_listing(self):
        for symbol in ("NVDA", " nvda ", "NVIDIA", "NVIDIA CORP", "NVIDIA CORPORATION"):
            with self.subTest(symbol=symbol):
                self.assertEqual(_normalize_market_symbol(symbol), "NVDA")

    def test_us_stock_and_canadian_cdr_use_separate_prices_and_currencies(self):
        def respond(request, timeout):
            symbol = "NVDA.TO" if "symbols=NVDA.TO" in request.full_url else "NVDA"
            price, currency = (41.49, "CAD") if symbol == "NVDA.TO" else (178.8, "USD")
            return BytesIO(json.dumps({"quoteResponse": {"result": [{
                "symbol": symbol, "regularMarketPrice": price, "currency": currency,
            }]}}).encode())

        with patch("app.main.urlopen", side_effect=respond):
            canadian_quote = get_market_quote("NVDA.TO")
            us_quote = get_market_quote("NVDA")

        self.assertEqual(canadian_quote, {
            "symbol": "NVDA.TO", "price": 41.49, "currency": "CAD", "source": "Yahoo Finance",
        })
        self.assertEqual(us_quote, {
            "symbol": "NVDA", "price": 178.8, "currency": "USD", "source": "Yahoo Finance",
        })

    def test_chart_fallback_keeps_canadian_listing(self):
        def respond(request, timeout):
            if "/v7/" in request.full_url:
                self.assertIn("symbols=NVDA.TO", request.full_url)
                raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)
            self.assertIn("/v8/finance/chart/NVDA.TO?", request.full_url)
            return BytesIO(json.dumps({"chart": {"result": [{"meta": {
                "symbol": "NVDA.TO", "regularMarketPrice": 41.49, "currency": "CAD",
            }}]}}).encode())

        with patch("app.main.urlopen", side_effect=respond):
            quote = get_market_quote("NVDA.TO")

        self.assertEqual(quote, {
            "symbol": "NVDA.TO", "price": 41.49,
            "currency": "CAD", "source": "Yahoo Finance Chart",
        })

    def test_tmx_fallback_uses_canadian_cdr(self):
        def respond(request, timeout):
            if "finance.yahoo.com" in request.full_url:
                raise HTTPError(request.full_url, 429, "Too Many Requests", {}, None)
            self.assertEqual(request.full_url, "https://r.jina.ai/http://money.tmx.com/en/quote/NVDA")
            return BytesIO(b"Nvidia CDR (CAD Hedged) (NVDA) | TSX Stock Price\nExchange:\nTSX\nPrice: $41.49\n")

        with patch("app.main.urlopen", side_effect=respond):
            quote = get_market_quote("NVDA.TO")

        self.assertEqual(quote, {
            "symbol": "NVDA", "price": 41.49, "currency": "CAD", "source": "TMX Money",
        })

    def test_canadian_provider_failure_does_not_use_us_fallbacks(self):
        def unavailable(request, timeout):
            raise HTTPError(request.full_url, 503, "Unavailable", {}, None)

        with (
            patch("app.main.urlopen", side_effect=unavailable),
            patch("app.main._fetch_nasdaq_stock_quote") as nasdaq,
            patch("app.main._fetch_stooq_quote") as stooq,
        ):
            with self.assertRaises(HTTPException) as raised:
                get_market_quote("NVDA.TO")

        self.assertEqual(raised.exception.status_code, 502)
        nasdaq.assert_not_called()
        stooq.assert_not_called()


class KiloQuoteTests(unittest.TestCase):
    def test_non_hedged_units_resolve_to_yahoo_listing(self):
        for symbol in ("KILO.B", " kilo.b ", "KILO.B.CA", "KILO.B.TSX", "KILO.B.TO", "KILO-B.TO"):
            with self.subTest(symbol=symbol):
                self.assertEqual(_normalize_market_symbol(symbol), "KILO-B.TO")

    def test_other_unit_classes_and_markets_are_preserved(self):
        for symbol in ("KILO.TO", "KILO.U", "KILO-U.TO", "BRK.B", "ALRIB.PA", "GOOG.TO"):
            with self.subTest(symbol=symbol):
                self.assertEqual(_normalize_market_symbol(symbol), symbol)

    def test_yahoo_chart_returns_cad_quote_after_quote_endpoint_fails(self):
        requests = []

        def respond(request, timeout):
            requests.append(request.full_url)
            if "/v7/" in request.full_url:
                raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)
            self.assertIn("/v8/finance/chart/KILO-B.TO?", request.full_url)
            return BytesIO(json.dumps({"chart": {"result": [{"meta": {
                "symbol": "KILO-B.TO", "regularMarketPrice": 72.12, "currency": "CAD",
            }}]}}).encode())

        with patch("app.main.urlopen", side_effect=respond):
            quote = get_market_quote("KILO.B")

        self.assertEqual(quote, {
            "symbol": "KILO-B.TO", "price": 72.12,
            "currency": "CAD", "source": "Yahoo Finance Chart",
        })
        self.assertEqual(len(requests), 2)
        self.assertIn("symbols=KILO-B.TO", requests[0])

    def test_tmx_fallback_uses_exchange_unit_class_symbol(self):
        requests = []

        def respond(request, timeout):
            requests.append(request.full_url)
            if "finance.yahoo.com" in request.full_url:
                raise HTTPError(request.full_url, 429, "Too Many Requests", {}, None)
            self.assertEqual(request.full_url, "https://r.jina.ai/http://money.tmx.com/en/quote/KILO.B")
            return BytesIO(b"Purpose Gold Bullion Fund (KILO.B) | TSX Stock Price\nExchange:\nTSX\nPrice: $72.12\n")

        with patch("app.main.urlopen", side_effect=respond):
            quote = get_market_quote("KILO.B")

        self.assertEqual(quote, {
            "symbol": "KILO.B", "price": 72.12,
            "currency": "CAD", "source": "TMX Money",
        })
        self.assertEqual(len(requests), 3)
        self.assertEqual(_normalize_symbol_for_tmx("KILO.B.TO"), "KILO.B")
        self.assertEqual(_normalize_symbol_for_tmx("CBIL.TO"), "CBIL")


if __name__ == "__main__":
    unittest.main()
