import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
import flet as ft

import app
from stock_data import StockDataError, get_stock_data, search_stock_symbol


DAILY_DATA = {
    "2026-10-14": {
        "1. open": "225.00",
        "2. high": "230.00",
        "3. low": "224.00",
        "4. close": "227.88",
    }
}


class StockDataTests(unittest.TestCase):
    def setUp(self):
        self.key_patch = patch("stock_data.API_KEY", "test-key")
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)
        self.request_patch = patch("stock_data.requests.get")
        self.request = self.request_patch.start()
        self.addCleanup(self.request_patch.stop)
        self.response = self.request.return_value

    def test_daily_prices_and_configured_key(self):
        self.response.json.return_value = {"Time Series (Daily)": DAILY_DATA}
        result = get_stock_data(" ibm ")
        self.assertEqual(result["2026-10-14"]["4. close"], 227.88)
        self.request.assert_called_once_with(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": "IBM",
                "apikey": "test-key",
                "outputsize": "compact",
            },
            timeout=15,
        )

    def test_searches_company_name_and_prefers_exact_match(self):
        self.response.json.return_value = {
            "bestMatches": [
                {"1. symbol": "AAPL", "2. name": "Apple Inc"},
                {"1. symbol": "APLE", "2. name": "Apple Hospitality REIT"},
            ]
        }
        self.assertEqual(search_stock_symbol(" Apple Inc "), ("AAPL", "Apple Inc"))
        self.request.assert_called_once_with(
            "https://www.alphavantage.co/query",
            params={
                "function": "SYMBOL_SEARCH",
                "keywords": "Apple Inc",
                "apikey": "test-key",
            },
            timeout=15,
        )

    def test_company_search_reports_no_matches(self):
        self.response.json.return_value = {"bestMatches": []}
        with self.assertRaisesRegex(StockDataError, "No stocks matched"):
            search_stock_symbol("Unknown Company")

    def test_provider_errors_are_explicit_and_redacted(self):
        for field in ("Error Message", "Note", "Information"):
            with self.subTest(field=field):
                self.response.json.return_value = {field: "Limit for test-key exceeded"}
                with self.assertRaisesRegex(StockDataError, r"Limit for \[REDACTED\] exceeded"):
                    get_stock_data("IBM")

    def test_transport_failures_do_not_expose_key(self):
        for error in (
            requests.Timeout("url with test-key"),
            requests.ConnectionError("url with test-key"),
        ):
            with self.subTest(error=type(error).__name__):
                self.request.side_effect = error
                with self.assertRaises(StockDataError) as caught:
                    get_stock_data("IBM")
                self.assertNotIn("test-key", str(caught.exception))

    def test_http_failure_does_not_expose_key(self):
        self.response.raise_for_status.side_effect = requests.HTTPError("url with test-key")
        with self.assertRaises(StockDataError) as caught:
            get_stock_data("IBM")
        self.assertNotIn("test-key", str(caught.exception))

    def test_invalid_json(self):
        self.response.json.side_effect = ValueError("Invalid JSON")
        with self.assertRaisesRegex(StockDataError, "invalid JSON"):
            get_stock_data("IBM")

    def test_missing_or_malformed_prices(self):
        for payload in (
            [],
            {},
            {"Time Series (Daily)": {}},
            {"Time Series (Daily)": {"2026-10-14": {}}},
            {"Time Series (Daily)": {"2026-10-14": []}},
            {"Time Series (Daily)": {"2026-10-14": {**DAILY_DATA["2026-10-14"], "4. close": "NaN"}}},
        ):
            with self.subTest(payload=payload):
                self.response.json.return_value = payload
                with self.assertRaises(StockDataError):
                    get_stock_data("IBM")

    def test_blank_symbol_and_key_make_no_request(self):
        with self.assertRaises(StockDataError):
            get_stock_data(" ")
        with patch("stock_data.API_KEY", ""):
            with self.assertRaises(StockDataError):
                get_stock_data("IBM")
        self.request.assert_not_called()


class AppTests(unittest.TestCase):
    def setUp(self):
        self.page = SimpleNamespace(window=SimpleNamespace(), add=Mock(), update=Mock())
        app.main(self.page)
        self.layout = self.page.add.call_args.args[0]
        search = self.layout.controls[1].content
        self.symbol, _, self.button = search.controls
        self.symbol.value = "IBM"
        self.error, self.price, self.chart, self.below = self.layout.controls[2:]

    def test_layout_stretches_chart_and_allows_scrolling(self):
        self.assertEqual(self.page.scroll, ft.ScrollMode.AUTO)
        self.assertEqual(self.layout.horizontal_alignment, ft.CrossAxisAlignment.STRETCH)
        with patch("app.get_stock_data", return_value=DAILY_DATA):
            self.button.on_click(None)
        chart_column = self.chart.content.content
        self.assertEqual(chart_column.horizontal_alignment, ft.CrossAxisAlignment.STRETCH)
        self.assertEqual(chart_column.controls[-1].height, 300)

    def test_fetch_builds_chart_and_shows_latest_date(self):
        with patch("app.get_stock_data", return_value=DAILY_DATA):
            self.button.on_click(None)
        self.assertFalse(self.error.visible)
        self.assertTrue(self.price.visible)
        self.assertTrue(self.chart.visible)
        self.assertTrue(self.below.visible)
        self.assertEqual(self.price.content.controls[1].value, "Date: 2026-10-14")
        chart = self.chart.content.content.controls[-1]
        self.assertEqual(len(chart.data_series[0].points), 1)
        self.assertEqual(chart.data_series[0].points[0].y, 227.88)
        self.assertTrue(chart.interactive)
        self.assertEqual(
            chart.data_series[0].points[0].tooltip,
            "2026-10-14\nClose: $227.88",
        )

    def test_fetch_resolves_company_name_to_symbol(self):
        with (
            patch("app.search_stock_symbol", return_value=("MSFT", "Microsoft Corporation")) as search,
            patch("app.get_stock_data", return_value=DAILY_DATA) as fetch,
        ):
            self.symbol.value = "Microsoft Corporation"
            self.button.on_click(None)
        search.assert_called_once_with("Microsoft Corporation")
        fetch.assert_called_once_with("MSFT")
        self.assertEqual(
            self.price.content.controls[0].value,
            "Stock: MSFT - Microsoft Corporation",
        )
        self.assertTrue(self.chart.visible)

    def test_fetch_searches_company_when_symbol_has_no_data(self):
        with (
            patch(
                "app.get_stock_data",
                side_effect=[
                    StockDataError("No daily stock data was returned for APPLE."),
                    DAILY_DATA,
                ],
            ) as fetch,
            patch("app.search_stock_symbol", return_value=("AAPL", "Apple Inc.")) as search,
        ):
            self.symbol.value = "Apple"
            self.button.on_click(None)
        search.assert_called_once_with("Apple")
        self.assertEqual(fetch.call_args_list[1].args, ("AAPL",))
        self.assertTrue(self.chart.visible)

    def test_fetch_searches_company_when_provider_rejects_single_word_symbol(self):
        with (
            patch(
                "app.get_stock_data",
                side_effect=[
                    StockDataError("Alpha Vantage: Invalid API call."),
                    DAILY_DATA,
                ],
            ) as fetch,
            patch("app.search_stock_symbol", return_value=("AAPL", "Apple Inc.")) as search,
        ):
            self.symbol.value = "Apple"
            self.button.on_click(None)
        search.assert_called_once_with("Apple")
        self.assertEqual(fetch.call_args_list[1].args, ("AAPL",))
        self.assertTrue(self.chart.visible)

    def test_hover_tooltips_match_dates_and_prices_in_selected_range(self):
        series = {
            f"2026-10-{day:02d}": {
                "1. open": 100.0,
                "2. high": 120.0,
                "3. low": 90.0,
                "4. close": 100.0 + day,
            }
            for day in range(14, 4, -1)
        }
        self.layout.controls[1].content.controls[1].value = "1 week"
        with patch("app.get_stock_data", return_value=series):
            self.button.on_click(None)
        chart = self.chart.content.content.controls[-1]
        points = chart.data_series[0].points
        self.assertTrue(chart.interactive)
        self.assertEqual(len(points), 7)
        for index, point in enumerate(points):
            day = index + 8
            with self.subTest(day=day):
                self.assertEqual(point.x, index)
                self.assertEqual(point.y, 100.0 + day)
                self.assertTrue(point.show_tooltip)
                self.assertEqual(
                    point.tooltip,
                    f"2026-10-{day:02d}\nClose: ${100.0 + day:.2f}",
                )
                point.before_update()
                self.assertEqual(point._internals["tooltip"].text, point.tooltip)

    def test_api_failure_hides_old_results(self):
        with patch("app.get_stock_data", return_value=DAILY_DATA):
            self.button.on_click(None)
        with patch("app.get_stock_data", side_effect=StockDataError("API rate limit reached")):
            self.button.on_click(None)
        self.assertTrue(self.error.visible)
        self.assertEqual(self.error.content.value, "API rate limit reached")
        self.assertFalse(self.price.visible)
        self.assertFalse(self.chart.visible)
        self.assertFalse(self.below.visible)


if __name__ == "__main__":
    unittest.main()
