from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from ..models import DataMode
@dataclass(frozen=True)
class DataResult:
    ticker: str
    bars: pd.DataFrame
    source: str
    mode: DataMode
    fetched_at: datetime
    last_timestamp: datetime | None
    stale: bool
    message: str = ""
class DataProvider(ABC):
    @abstractmethod
    def get_daily(self, ticker: str, start: str, end: str | None = None) -> DataResult: ...
