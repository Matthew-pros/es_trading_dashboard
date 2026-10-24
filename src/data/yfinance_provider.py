from __future__ import annotations
from datetime import datetime, timezone
import time
import pandas as pd
import yfinance as yf
from .base import DataProvider, DataResult
from .cache import CsvCache
from ..indicators import normalize_ohlcv
from ..models import DataMode
class YahooFinanceProvider(DataProvider):
    def __init__(self, cache: CsvCache | None = None, retries: int = 3, cache_ttl_seconds: int = 900):
        self.cache = cache or CsvCache()
        self.retries = max(1, retries)
        self.cache_ttl_seconds = cache_ttl_seconds
    def get_daily(self, ticker: str, start: str, end: str | None = None) -> DataResult:
        key = f"{ticker}|{start}|{end or ''}|auto_adjust=False|daily"
        cached = self.cache.get(key)
        now = datetime.now(timezone.utc)
        if cached is not None:
            modified = self.cache._path(key).stat().st_mtime
            age = now.timestamp() - modified
            if age <= self.cache_ttl_seconds:
                bars = normalize_ohlcv(cached)
                return DataResult(ticker, bars, "Yahoo Finance cache", DataMode.HISTORICAL, now, bars.index[-1].to_pydatetime() if len(bars) else None, False, f"Cache age {age:.0f}s")
        last_error = "unknown error"
        for attempt in range(self.retries):
            try:
                raw = yf.download(ticker, start=start, end=end, interval="1d", auto_adjust=False, actions=True, progress=False, threads=False, group_by="column")
                if raw is None or raw.empty: raise ValueError("Yahoo Finance returned no daily bars.")
                if isinstance(raw.columns, pd.MultiIndex): raw.columns = [str(col[0]) for col in raw.columns]
                raw = raw[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]].copy()
                raw = normalize_ohlcv(raw)
                if raw.empty: raise ValueError("No valid OHLCV bars after normalization.")
                self.cache.put(key, raw)
                fetched = datetime.now(timezone.utc)
                return DataResult(ticker, raw, "Yahoo Finance", DataMode.HISTORICAL, fetched, raw.index[-1].to_pydatetime(), False, "Yahoo historical data; not live.")
            except Exception as exc:
                last_error = str(exc)
                if attempt + 1 < self.retries: time.sleep(min(0.5 * 2**attempt, 3.0))
        raise RuntimeError(f"Yahoo Finance data for {ticker} unavailable after {self.retries} attempts: {last_error}")
