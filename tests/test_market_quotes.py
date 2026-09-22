import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from app.main import _normalize_market_symbol, _normalize_symbol_for_tmx, get_market_quote


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
