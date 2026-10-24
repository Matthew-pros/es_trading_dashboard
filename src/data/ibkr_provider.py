from __future__ import annotations
from datetime import datetime, timezone
import os
import pandas as pd
from .base import DataProvider, DataResult
from ..indicators import normalize_ohlcv
from ..models import DataMode
class IBKRProvider(DataProvider):
    """Read-only IBKR history provider. Never submits orders."""
    def __init__(self, host: str | None = None, port: int | None = None, client_id: int | None = None, timeout: float = 5.0):
        self.host = host or os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = int(port if port is not None else (os.getenv("IBKR_PORT") or "7497"))
        self.client_id = int(client_id if client_id is not None else (os.getenv("IBKR_CLIENT_ID") or "71"))
        self.timeout = timeout
    def get_daily(self, ticker: str, start: str, end: str | None = None) -> DataResult:
        try:
            from ib_async import IB, Stock, util
        except ImportError as exc:
            raise RuntimeError("IBKR provider vyžaduje knihovnu ib_async.") from exc
        ib = IB()
        try:
            ib.connect(self.host or "127.0.0.1", self.port, clientId=self.client_id, timeout=self.timeout, readonly=True)
            contract = Stock(ticker, "SMART", "USD")
            qualified = ib.qualifyContracts(contract)
            if not qualified: raise RuntimeError(f"IBKR contract qualification failed for {ticker}.")
            bars = ib.reqHistoricalData(qualified[0], endDateTime="", durationStr="2 Y", barSizeSetting="1 day", whatToShow="TRADES", useRTH=True, formatDate=1, keepUpToDate=False)
            if not bars: raise RuntimeError(f"IBKR returned no history for {ticker}; check subscription and permissions.")
            frame = util.df(bars).rename(columns={"date":"Date"}).set_index("date") if "date" in util.df(bars).columns else util.df(bars).set_index("date")
            frame = frame.rename(columns={"open":"Open", "high":"High", "low":"Low", "close":"Close", "volume":"Volume"})
            frame = normalize_ohlcv(frame)
            frame = frame.loc[frame.index >= pd.Timestamp(start)]
            if end: frame = frame.loc[frame.index < pd.Timestamp(end)]
            if frame.empty: raise RuntimeError(f"IBKR returned no usable bars for {ticker} in requested range.")
            # Historical data request is conservatively labeled HISTORICAL; live status needs a separately verified streaming market-data type.
            now = datetime.now(timezone.utc)
            return DataResult(ticker, frame, "IBKR historical", DataMode.HISTORICAL, now, frame.index[-1].to_pydatetime(), False, "Historical bars; feed type not assumed live.")
        except Exception as exc:
            raise RuntimeError(f"IBKR history request failed for {ticker}: {exc}") from exc
        finally:
            if ib.isConnected(): ib.disconnect()
