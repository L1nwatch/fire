import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from fastapi import HTTPException
from app import db, exchange_rates as fx


def observation(day, cny='0.2094', usd='1.4021', eur='1.6086'):
    return {'d': day, 'FXCNYCAD': {'v': cny}, 'FXUSDCAD': {'v': usd}, 'FXEURCAD': {'v': eur}}


class ExchangeRateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        path = Path(self.directory.name) / 'fire.sqlite3'
        self.connection_patch = patch('app.exchange_rates.connect', side_effect=lambda: db.connect(path))
        self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.today = datetime.now(timezone.utc).date().isoformat()

    def fetch(self, rows):
        with patch('app.exchange_rates.urlopen', return_value=BytesIO(json.dumps({'observations': rows}).encode())):
            return fx.get_exchange_rates()

    def test_latest_complete_observation_and_cad_base_are_persisted(self):
        old = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        state = self.fetch([observation(old, '0.20'), observation(self.today)])
        self.assertEqual(state['date'], self.today)
        self.assertEqual(state['rates'], {'CAD': 1, 'CNY': 0.2094, 'USD': 1.4021, 'EUR': 1.6086})
        self.assertFalse(state['stale'])
        with patch('app.exchange_rates.urlopen', side_effect=AssertionError('Fresh cache must not fetch')):
            self.assertEqual(fx.get_exchange_rates(), state)
        self.assertEqual(fx._read_cache()['rates'], state['rates'])

    def test_partial_or_invalid_latest_rows_never_mix_observation_dates(self):
        old = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        for value in (None, '', '0', '-1', 'NaN', 'Infinity'):
            with self.subTest(value=value), patch('app.exchange_rates.urlopen', return_value=BytesIO(json.dumps({
                'observations': [observation(self.today, value), observation(old)],
            }).encode())):
                self.assertEqual(fx._fetch_rates()['date'], old)

    def test_unavailable_provider_returns_503_without_invented_rates(self):
        with patch('app.exchange_rates.urlopen', side_effect=URLError('offline')):
            with self.assertRaises(HTTPException) as caught:
                fx.get_exchange_rates()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIsNone(fx._read_cache())

    def test_failed_refresh_preserves_last_good_rates_and_marks_stale(self):
        self.fetch([observation(self.today)])
        cached = fx._read_cache()
        cached['fetchedAt'] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        fx._write_cache(cached)
        with patch('app.exchange_rates.urlopen', side_effect=URLError('offline')):
            result = fx.get_exchange_rates()
        self.assertTrue(result['stale'])
        self.assertEqual(result['rates'], cached['rates'])
        self.assertEqual(result['fetchedAt'], cached['fetchedAt'])
        self.assertEqual(fx._read_cache(), cached)

    def test_successful_refresh_replaces_old_cache(self):
        self.fetch([observation(self.today, '0.20')])
        cached = fx._read_cache()
        cached['fetchedAt'] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        fx._write_cache(cached)
        self.assertEqual(self.fetch([observation(self.today)])['rates']['CNY'], 0.2094)

    def test_old_observations_are_flagged_even_when_provider_responds(self):
        old = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
        self.assertTrue(self.fetch([observation(old)])['stale'])

    def test_malformed_payload_does_not_overwrite_cache(self):
        with patch('app.exchange_rates.urlopen', return_value=BytesIO(b'not json')):
            with self.assertRaises(HTTPException):
                fx.get_exchange_rates()
        self.assertIsNone(fx._read_cache())
