"""Fetch daily OHLC data using config.API_KEY.

Alpha Vantage's compact response contains the latest 100 trading sessions,
not intraday quotes or full history. API errors are raised as StockDataError.
"""

import math

import requests

from config import API_KEY


class StockDataError(Exception):
    """A stock-data request failed or returned unusable data."""


def get_stock_data(symbol: str) -> dict[str, dict[str, float]]:
    symbol = symbol.strip().upper()
    if not symbol:
        raise StockDataError("Please enter a stock symbol.")
    data = _request_alpha_vantage(
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
        }
    )

    series = data.get("Time Series (Daily)")
    if not isinstance(series, dict) or not series:
        raise StockDataError(f"No daily stock data was returned for {symbol}.")

    result: dict[str, dict[str, float]] = {}
    fields = ("1. open", "2. high", "3. low", "4. close")
    for date, record in series.items():
        if not isinstance(date, str) or not isinstance(record, dict):
            raise StockDataError("Alpha Vantage returned malformed daily stock data.")
        try:
            prices = {field: float(record[field]) for field in fields}
        except (KeyError, TypeError, ValueError, OverflowError):
            raise StockDataError("Alpha Vantage returned malformed daily prices.") from None
        if any(not math.isfinite(price) or price <= 0 for price in prices.values()):
            raise StockDataError("Alpha Vantage returned invalid daily prices.")
        result[date] = prices
    return result


def search_stock_symbol(query: str) -> tuple[str, str]:
    query = query.strip()
    if not query:
        raise StockDataError("Please enter a company name or stock symbol.")

    data = _request_alpha_vantage(
        {
            "function": "SYMBOL_SEARCH",
            "keywords": query,
        }
    )
    matches = data.get("bestMatches")
    if not isinstance(matches, list):
        raise StockDataError(f"No stocks matched '{query}'. Try a ticker symbol.")

    valid_matches = [
        match for match in matches
        if isinstance(match, dict)
        and isinstance(match.get("1. symbol"), str)
        and match["1. symbol"].strip()
        and isinstance(match.get("2. name"), str)
        and match["2. name"].strip()
    ]
    if not valid_matches:
        raise StockDataError(f"No stocks matched '{query}'. Try a ticker symbol.")

    match = next(
        (
            candidate
            for candidate in valid_matches
            if candidate["2. name"].strip().casefold() == query.casefold()
        ),
        valid_matches[0],
    )
    return match["1. symbol"].strip().upper(), match["2. name"].strip()


def _request_alpha_vantage(params: dict[str, str]) -> dict:
    if not isinstance(API_KEY, str) or not API_KEY.strip():
        raise StockDataError("Set API_KEY in config.py before fetching stock data.")

    request_params = {**params, "apikey": API_KEY.strip()}
    try:
        response = requests.get(
            "https://www.alphavantage.co/query",
            params=request_params,
            timeout=15,
        )
        response.raise_for_status()
    except requests.Timeout:
        raise StockDataError("The stock-data request timed out. Please try again.") from None
    except requests.RequestException:
        raise StockDataError(
            "Unable to reach Alpha Vantage. Check your connection and try again."
        ) from None

    try:
        data = response.json()
    except ValueError:
        raise StockDataError("Alpha Vantage returned an invalid JSON response.") from None
    if not isinstance(data, dict):
        raise StockDataError("Alpha Vantage returned an unexpected response.")

    for field in ("Error Message", "Note", "Information"):
        if data.get(field):
            message = str(data[field]).replace(API_KEY.strip(), "[REDACTED]")
            raise StockDataError(f"Alpha Vantage: {message}")
    return data
